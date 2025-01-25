from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import os
import httpx
from dotenv import load_dotenv

from .database import init_db, async_session, Conversation
from .dify_client import DifyClient

load_dotenv()

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize Dify client
dify_client = DifyClient()

# Dependency to get database session
async def get_db():
    async with async_session() as session:
        yield session

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    timestamp: datetime

class ConversationResponse(BaseModel):
    id: str
    user_message: str
    assistant_message: str
    timestamp: datetime
    conversation_id: str

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        try:
            print(f"Received chat request: {request}")
            # Call Dify API
            dify_response = await dify_client.chat(
                message=request.message,
                conversation_id=request.conversation_id
            )
            print(f"Dify API Response: {dify_response}")

            # Extract the response data
            print(f"Raw Dify response: {dify_response}")
            answer = ""
            if isinstance(dify_response, dict):
                answer = (
                    dify_response.get("answer", "") or
                    dify_response.get("response", "") or
                    dify_response.get("message", {}).get("content", "") if isinstance(dify_response.get("message"), dict) else ""
                )
            
            conv_id = (
                dify_response.get("conversation_id", "") or
                dify_response.get("id", "") or
                str(uuid.uuid4())
            )

            # Create new conversation record
            conversation = Conversation(
                id=str(uuid.uuid4()),
                user_message=request.message,
                assistant_message=answer,
                conversation_id=conv_id,
                timestamp=datetime.utcnow()
            )

            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

            print(f"Created conversation record: {conversation.id}")
            return ChatResponse(
                conversation_id=conversation.conversation_id,
                message=conversation.assistant_message,
                timestamp=conversation.timestamp
            )
        except Exception as e:
            print(f"Error in chat endpoint: {str(e)}")
            if isinstance(e, httpx.HTTPError):
                print(f"HTTP Error response: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history", response_model=List[ConversationResponse])
async def get_chat_history(
    limit: int = 50,
    before: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = db.query(Conversation)
        if before:
            query = query.filter(Conversation.timestamp < before)
        conversations = await query.order_by(Conversation.timestamp.desc()).limit(limit).all()
        
        return [
            ConversationResponse(
                id=conv.id,
                user_message=conv.user_message,
                assistant_message=conv.assistant_message,
                timestamp=conv.timestamp,
                conversation_id=conv.conversation_id
            )
            for conv in conversations
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
