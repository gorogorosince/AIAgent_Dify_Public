from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import async_session, SlackWorkspace, SlackChannel, SlackMessage
from .slack_client import SlackClient
import secrets
import hashlib
import hmac
import time
import uuid
import json
from datetime import datetime
from typing import Dict, Optional, Any

router = APIRouter()
slack_client = SlackClient()

# Dictionary to store state parameters and their creation timestamps
state_store: Dict[str, float] = {}

# Dependency to get database session
async def get_db():
    async with async_session() as session:
        yield session

def generate_state_param() -> str:
    """Generate a secure state parameter for OAuth flow."""
    state = secrets.token_urlsafe(32)
    state_store[state] = time.time()
    return state

def verify_state_param(state: str) -> bool:
    """Verify the state parameter is valid and not expired."""
    timestamp = state_store.get(state)
    if not timestamp:
        return False
    
    # Remove state after use
    del state_store[state]
    
    # Check if state is not older than 10 minutes
    return (time.time() - timestamp) < 600

def verify_slack_signature(request: Request) -> bool:
    """Verify that the request came from Slack."""
    slack_signing_secret = slack_client.signing_secret.encode()
    slack_signature = request.headers.get("X-Slack-Signature", "")
    slack_timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    
    if abs(time.time() - int(slack_timestamp)) > 60 * 5:
        return False
        
    sig_basestring = f"v0:{slack_timestamp}:{request.body.decode()}"
    my_signature = 'v0=' + hmac.new(
        slack_signing_secret,
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, slack_signature)

@router.get("/slack/install")
async def install_slack_app():
    """Generate Slack app installation URL."""
    state = generate_state_param()
    install_url = slack_client.get_install_url(state)
    return {"install_url": install_url}

@router.get("/slack/oauth/callback")
async def slack_oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback from Slack."""
    if not verify_state_param(state):
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    try:
        # Exchange code for access token
        token_response = await slack_client.exchange_code_for_token(code)
        
        if not token_response.get("ok"):
            raise HTTPException(
                status_code=400,
                detail=f"Slack error: {token_response.get('error')}"
            )
        
        # Extract workspace information
        team = token_response["team"]
        workspace = await slack_client.save_workspace(
            db=db,
            team_id=team["id"],
            team_name=team["name"],
            access_token=token_response["access_token"],
            bot_user_id=token_response["bot_user_id"],
            scope=token_response["scope"],
            incoming_webhook_url=token_response.get("incoming_webhook", {}).get("url"),
            incoming_webhook_channel=token_response.get("incoming_webhook", {}).get("channel")
        )
        
        # Fetch and store channels
        await slack_client.get_channel_list(
            token=workspace.access_token,
            db=db,
            workspace_id=workspace.id
        )
        
        return {
            "ok": True,
            "team_id": team["id"],
            "team_name": team["name"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/slack/events")
async def slack_events(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Slack events and commands."""
    if not verify_slack_signature(request):
        raise HTTPException(status_code=401, detail="Invalid request signature")
    
    body = await request.json()
    
    # Handle URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body["challenge"]}
    
    # Handle events
    if body.get("type") == "event_callback":
        event = body.get("event", {})
        event_type = event.get("type")
        
        # Handle both direct messages and app mentions
        if event_type in ["message", "app_mention"]:
            # Ignore bot messages and message_changed events
            if event.get("subtype") in ["bot_message", "message_changed"]:
                return {"ok": True}
            
            # Extract message details
            channel_id = event.get("channel")
            user_id = event.get("user")
            text = event.get("text", "")
            ts = event.get("ts")
            thread_ts = event.get("thread_ts")
            team_id = body.get("team_id")
            
            try:
                # Get workspace and channel info
                workspace_result = await db.execute(
                    select(SlackWorkspace).where(SlackWorkspace.id == team_id)
                )
                workspace = workspace_result.scalar_one_or_none()
                
                if not workspace:
                    raise HTTPException(status_code=404, detail="Workspace not found")
                
                channel_result = await db.execute(
                    select(SlackChannel).where(
                        SlackChannel.id == channel_id,
                        SlackChannel.workspace_id == team_id
                    )
                )
                channel = channel_result.scalar_one_or_none()
                
                if not channel:
                    # Create channel if it doesn't exist
                    channel = SlackChannel(
                        id=channel_id,
                        name=f"channel-{channel_id}",  # Default name
                        workspace_id=team_id,
                        is_private=False
                    )
                    db.add(channel)
                
                # Create SlackMessage record
                message = SlackMessage(
                    id=str(uuid.uuid4()),
                    channel_id=channel_id,
                    user_id=user_id,
                    text=text,
                    ts=ts,
                    thread_ts=thread_ts,
                    created_at=datetime.utcnow()
                )
                db.add(message)
                await db.commit()
                
                # Store the conversation mapping for future responses
                if thread_ts:
                    # If in a thread, use thread_ts as conversation identifier
                    conversation_id = f"slack-{team_id}-{channel_id}-{thread_ts}"
                else:
                    # If not in a thread, create a new conversation
                    conversation_id = f"slack-{team_id}-{channel_id}-{ts}"
                
                message.conversation_id = conversation_id
                await db.commit()
                
                return {"ok": True}
                
            except Exception as e:
                print(f"Error processing message event: {str(e)}")
                await db.rollback()
                raise HTTPException(status_code=500, detail=str(e))
    
    # Handle slash commands
    elif body.get("type") == "command":
        command = body.get("command")
        text = body.get("text", "").strip()
        channel_id = body.get("channel_id")
        user_id = body.get("user_id")
        team_id = body.get("team_id")
        
        try:
            # Get workspace info
            workspace_result = await db.execute(
                select(SlackWorkspace).where(SlackWorkspace.id == team_id)
            )
            workspace = workspace_result.scalar_one_or_none()
            
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")
            
            # Create SlackMessage record for the command
            message = SlackMessage(
                id=str(uuid.uuid4()),
                channel_id=channel_id,
                user_id=user_id,
                text=f"{command} {text}".strip(),
                ts=str(time.time()),
                created_at=datetime.utcnow(),
                conversation_id=f"slack-{team_id}-{channel_id}-{time.time()}"
            )
            db.add(message)
            await db.commit()
            
            return {
                "response_type": "in_channel",
                "text": "処理中です..."  # "Processing..."
            }
            
        except Exception as e:
            print(f"Error processing slash command: {str(e)}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    return {"ok": True}

@router.post("/slack/interactivity")
async def slack_interactivity(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Slack interactive components like buttons and modals."""
    if not verify_slack_signature(request):
        raise HTTPException(status_code=401, detail="Invalid request signature")
    
    try:
        form = await request.form()
        payload = json.loads(form.get("payload", "{}"))
        
        # Extract common fields
        team_id = payload.get("team", {}).get("id")
        channel_id = payload.get("channel", {}).get("id")
        user_id = payload.get("user", {}).get("id")
        action_type = payload.get("type")
        
        if team_id and channel_id and user_id:
            # Get workspace info
            workspace_result = await db.execute(
                select(SlackWorkspace).where(SlackWorkspace.id == team_id)
            )
            workspace = workspace_result.scalar_one_or_none()
            
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")
            
            # Store interaction in database
            message = SlackMessage(
                id=str(uuid.uuid4()),
                channel_id=channel_id,
                user_id=user_id,
                text=f"Interactive action: {action_type}",
                ts=str(time.time()),
                created_at=datetime.utcnow(),
                conversation_id=f"slack-{team_id}-{channel_id}-{time.time()}"
            )
            db.add(message)
            await db.commit()
        
        return {"ok": True}
        
    except Exception as e:
        print(f"Error processing interactive component: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
