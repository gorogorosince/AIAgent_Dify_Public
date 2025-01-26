from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from .database import async_session
from .slack_client import SlackClient
import secrets
import hashlib
import hmac
import time
from typing import Dict

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
    
    # TODO: Handle other event types
    return {"ok": True}
