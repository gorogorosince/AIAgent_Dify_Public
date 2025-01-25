import httpx
import os
from typing import Optional

class DifyClient:
    def __init__(self):
        self.api_key = os.getenv("DIFY_API_KEY")
        self.base_url = "https://api.dify.ai/v1"
        if not self.api_key:
            raise ValueError("DIFY_API_KEY must be set")

    async def chat(self, message: str, conversation_id: Optional[str] = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": {},
            "query": message,
            "user": "default_user",
            "response_mode": "blocking",
            "conversation_id": conversation_id if conversation_id else None,
            "stream": False
        }

        try:
            async with httpx.AsyncClient() as client:
                endpoint = f"{self.base_url}/v1/chat-messages"
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
                print(f"Dify API Response: {data}")
                
                return {
                    "answer": data.get("answer", ""),
                    "conversation_id": data.get("conversation_id", "")
                }
        except httpx.HTTPError as e:
            print(f"HTTP Error: {str(e)}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            raise
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            raise
