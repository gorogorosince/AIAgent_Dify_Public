from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    user_message = Column(String, nullable=False)
    assistant_message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    conversation_id = Column(String, nullable=False)
    # Add relationship to SlackMessage if message originated from Slack
    slack_channel_id = Column(String, ForeignKey('slack_channels.id'), nullable=True)
    slack_thread_ts = Column(String, nullable=True)

class SlackWorkspace(Base):
    __tablename__ = "slack_workspaces"

    id = Column(String, primary_key=True)  # Workspace/Team ID from Slack
    name = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    bot_user_id = Column(String, nullable=False)
    bot_scope = Column(String, nullable=False)
    incoming_webhook_url = Column(String, nullable=True)
    incoming_webhook_channel = Column(String, nullable=True)
    installed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    channels = relationship("SlackChannel", back_populates="workspace")

class SlackChannel(Base):
    __tablename__ = "slack_channels"

    id = Column(String, primary_key=True)  # Channel ID from Slack
    name = Column(String, nullable=False)
    workspace_id = Column(String, ForeignKey('slack_workspaces.id'), nullable=False)
    is_private = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    workspace = relationship("SlackWorkspace", back_populates="channels")
    conversations = relationship("Conversation")

class SlackMessage(Base):
    __tablename__ = "slack_messages"

    id = Column(String, primary_key=True)
    channel_id = Column(String, ForeignKey('slack_channels.id'), nullable=False)
    user_id = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    ts = Column(String, nullable=False)  # Slack's timestamp ID
    thread_ts = Column(String, nullable=True)  # Parent thread timestamp if in thread
    conversation_id = Column(String, ForeignKey('conversations.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
