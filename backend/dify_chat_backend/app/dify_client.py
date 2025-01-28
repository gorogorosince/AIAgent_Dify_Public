import httpx
import os
import json
import uuid
from typing import Optional, Dict, AsyncGenerator

class DifyClient:
    def __init__(self):
        self.api_key = os.getenv("DIFY_API_KEY", "test-api-key")  # Use test key for tests
        self.base_url = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
        
        # Only check for API key in non-test environments
        if not self.api_key and not os.getenv("PYTEST_CURRENT_TEST"):
            raise ValueError("DIFY_API_KEY must be set")

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        source: str = "web"
    ) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Generate a unique user identifier based on source and user_id
        user_identifier = f"{source}-{user_id}" if user_id else "default-user"
        
        payload = {
            "inputs": {},
            "query": message,
            "user": user_identifier,
            "response_mode": "blocking",  # Changed to blocking mode
            "conversation_id": conversation_id if conversation_id else None
        }
        
        print(f"Request payload structure: {list(payload.keys())}")

        try:
            async with httpx.AsyncClient() as client:
                endpoint = f"{self.base_url}/chat-messages"
                print(f"Sending request to Dify API: {endpoint}")
                print(f"Payload: {payload}")
                print(f"Headers: {headers}")
                
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract answer and conversation_id from response
                answer = data.get("answer", "")
                current_conversation_id = (
                    data.get("conversation_id") or
                    data.get("id") or
                    conversation_id or
                    str(uuid.uuid4())
                )
                
                return {
                    "answer": answer.strip(),
                    "conversation_id": current_conversation_id
                }
                    
        except httpx.HTTPError as e:
            print(f"HTTP Error: {str(e)}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            raise
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            raise
