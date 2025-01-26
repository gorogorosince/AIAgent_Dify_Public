import os
from typing import Optional, Dict, Any
import httpx
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import SlackWorkspace, SlackChannel

class SlackClient:
    def __init__(self):
        self.client_id = os.getenv("SLACK_CLIENT_ID", "8246956134146.8353298906100")
        self.client_secret = os.getenv("SLACK_CLIENT_SECRET", "9e9b66ce96e2b3a6f85d72b719565cb4")
        self.signing_secret = os.getenv("SLACK_SIGNING_SECRET", "50283a9a479984c449968fa8378f7673")
        self.base_url = "https://slack.com/api"

    def get_install_url(self, state: str) -> str:
        """Generate Slack app installation URL."""
        scopes = [
            "chat:write",
            "channels:read",
            "commands",
            "incoming-webhook",
            "im:history",
            "im:write"
        ]
        
        return (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={self.client_id}"
            f"&scope={','.join(scopes)}"
            f"&state={state}"
        )

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange temporary code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth.v2.access",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code
                }
            )
            response.raise_for_status()
            return response.json()

    async def save_workspace(
        self, 
        db: AsyncSession,
        team_id: str,
        team_name: str,
        access_token: str,
        bot_user_id: str,
        scope: str,
        incoming_webhook_url: Optional[str] = None,
        incoming_webhook_channel: Optional[str] = None
    ) -> SlackWorkspace:
        """Save or update workspace information."""
        # Check if workspace already exists
        result = await db.execute(
            select(SlackWorkspace).where(SlackWorkspace.id == team_id)
        )
        workspace = result.scalar_one_or_none()

        if workspace:
            # Update existing workspace
            workspace.name = team_name
            workspace.access_token = access_token
            workspace.bot_user_id = bot_user_id
            workspace.bot_scope = scope
            workspace.incoming_webhook_url = incoming_webhook_url
            workspace.incoming_webhook_channel = incoming_webhook_channel
            workspace.is_active = True
        else:
            # Create new workspace
            workspace = SlackWorkspace(
                id=team_id,
                name=team_name,
                access_token=access_token,
                bot_user_id=bot_user_id,
                bot_scope=scope,
                incoming_webhook_url=incoming_webhook_url,
                incoming_webhook_channel=incoming_webhook_channel,
                installed_at=datetime.utcnow(),
                is_active=True
            )
            db.add(workspace)

        await db.commit()
        await db.refresh(workspace)
        return workspace

    async def post_message(
        self,
        token: str,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Post a message to a Slack channel."""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }
            
            data = {
                "channel": channel,
                "text": text,
            }
            if thread_ts:
                data["thread_ts"] = thread_ts

            response = await client.post(
                f"{self.base_url}/chat.postMessage",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()

    async def get_channel_list(
        self,
        token: str,
        db: AsyncSession,
        workspace_id: str
    ) -> list[SlackChannel]:
        """Fetch and store channel list for a workspace."""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            response = await client.get(
                f"{self.base_url}/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel"}
            )
            response.raise_for_status()
            data = response.json()

            channels = []
            for channel in data.get("channels", []):
                # Check if channel already exists
                result = await db.execute(
                    select(SlackChannel).where(
                        SlackChannel.id == channel["id"],
                        SlackChannel.workspace_id == workspace_id
                    )
                )
                existing_channel = result.scalar_one_or_none()

                if existing_channel:
                    # Update existing channel
                    existing_channel.name = channel["name"]
                    existing_channel.is_private = channel.get("is_private", False)
                    existing_channel.is_active = True
                    channels.append(existing_channel)
                else:
                    # Create new channel
                    new_channel = SlackChannel(
                        id=channel["id"],
                        name=channel["name"],
                        workspace_id=workspace_id,
                        is_private=channel.get("is_private", False),
                        created_at=datetime.utcnow(),
                        is_active=True
                    )
                    db.add(new_channel)
                    channels.append(new_channel)

            await db.commit()
            return channels
