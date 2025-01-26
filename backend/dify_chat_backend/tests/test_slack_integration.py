import os
import pytest
from dotenv import load_dotenv
import hmac
import hashlib
import json
import time
import secrets
from unittest.mock import AsyncMock, patch
from app.slack_routes import state_store

# Load test environment variables before importing app
load_dotenv("tests/.env.test", override=True)

from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, async_session

@pytest.fixture
async def test_client():
    """Test client fixture with database setup and teardown."""
    # Setup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create test client
    client = TestClient(app)
    
    # Provide the client to the test
    yield client
    
    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # Clear any remaining connections
    await engine.dispose()

def generate_slack_signature(secret: str, timestamp: str, body: str) -> str:
    sig_basestring = f"v0:{timestamp}:{body}"
    signature = 'v0=' + hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

@pytest.mark.asyncio
async def test_slack_install_url(test_client):
    response = test_client.get("/api/slack/install")
    assert response.status_code == 200
    assert "install_url" in response.json()
    assert "state" in response.json()["install_url"]

@pytest.mark.asyncio
async def test_slack_oauth_callback_invalid_state(test_client):
    response = test_client.get("/api/slack/oauth/callback?code=test_code&state=invalid_state")
    assert response.status_code == 400
    assert "Invalid state parameter" in response.json()["detail"]

def test_slack_events_invalid_signature(test_client):
    body = {"type": "url_verification", "challenge": "test_challenge"}
    body_str = json.dumps(body)
    timestamp = str(int(time.time()))
    
    response = test_client.post(
        "/api/slack/events",
        content=body_str.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": "invalid_signature"
        }
    )
    assert response.status_code == 401
    assert "Invalid request signature" in response.json()["detail"]

def test_slack_events_url_verification(test_client):
    challenge = "test_challenge"
    body = {"type": "url_verification", "challenge": challenge}
    body_str = json.dumps(body)
    timestamp = str(int(time.time()))
    
    signature = generate_slack_signature(
        "50283a9a479984c449968fa8378f7673",  # Test signing secret
        timestamp,
        body_str
    )
    
    response = test_client.post(
        "/api/slack/events",
        content=body_str.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"challenge": challenge}

@patch('app.slack_routes.slack_client.post_message')
@patch('app.dify_client.DifyClient.chat')
@patch('app.slack_client.SlackClient.exchange_code_for_token')
def test_slack_message_event(mock_exchange_token, mock_dify_chat, mock_post_message, test_client):
    # Mock token exchange
    mock_exchange_token.return_value = {
        "ok": True,
        "team": {
            "id": "T123456",
            "name": "Test Workspace"
        },
        "access_token": "xoxb-test-token",
        "bot_user_id": "U123BOT",
        "scope": "chat:write,channels:read"
    }
    # Mock Dify response
    mock_dify_chat.return_value = {
        "answer": "Test response",
        "conversation_id": "test_conv_id"
    }
    
    # Mock Slack post message
    mock_post_message.return_value = {"ok": True}
    
    # Create test workspace by simulating OAuth callback
    state = secrets.token_urlsafe(32)
    state_store[state] = time.time()  # Store state for validation
    
    response = test_client.get(f"/api/slack/oauth/callback?code=test_code&state={state}")
    assert response.status_code == 200
    
    body = {
        "type": "event_callback",
        "team_id": "T123456",
        "event": {
            "type": "message",
            "channel": "C123456",
            "user": "U123456",
            "text": "Hello bot",
            "ts": "1234567890.123456"
        }
    }
    
    body_str = json.dumps(body)
    timestamp = str(int(time.time()))
    signature = generate_slack_signature(
        "50283a9a479984c449968fa8378f7673",  # Test signing secret
        timestamp,
        body_str
    )
    
    response = test_client.post(
        "/api/slack/events",
        content=body_str.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    
    # Verify Dify was called
    mock_dify_chat.assert_called_once()
    # Verify Slack message was sent
    mock_post_message.assert_called_once()
