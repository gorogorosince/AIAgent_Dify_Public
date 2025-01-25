# API Specification

## Dify Integration Details
- Base URL: https://api.dify.ai/v1
- Authentication: API Key (app-uB8sJEGbxHaQnANzpA8bArBm)

## Backend API Endpoints

### POST /api/chat
Sends a message to Dify and stores the conversation history.

Request:
```json
{
  "message": string,
  "conversation_id": string | null
}
```

Response:
```json
{
  "conversation_id": string,
  "message": string,
  "timestamp": string
}
```

### GET /api/chat/history
Retrieves conversation history.

Query Parameters:
- limit (optional): number of messages to return
- before (optional): timestamp to get messages before

Response:
```json
{
  "conversations": [
    {
      "id": string,
      "user_message": string,
      "assistant_message": string,
      "timestamp": string,
      "conversation_id": string
    }
  ]
}
```

## Database Schema (SQLite)

```sql
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_message TEXT NOT NULL,
    assistant_message TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    conversation_id TEXT NOT NULL
);

CREATE INDEX idx_conversation_id ON conversations(conversation_id);
CREATE INDEX idx_timestamp ON conversations(timestamp);
```

## Data Flow
1. Frontend sends message to backend `/api/chat`
2. Backend forwards message to Dify API
3. Backend stores both user message and Dify response
4. Backend returns Dify response to frontend
5. Frontend updates UI with new message
6. Frontend can fetch history using `/api/chat/history`

## Environment Variables
```
DIFY_API_KEY=app-uB8sJEGbxHaQnANzpA8bArBm
DIFY_API_URL=https://api.dify.ai/v1
DATABASE_URL=sqlite:///./chat.db
```
