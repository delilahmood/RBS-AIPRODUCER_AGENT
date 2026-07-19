import httpx
from typing import Optional, List
from app.config import QWEN_API_KEY, QWEN_BASE_URL

class AIService:
    def __init__(self):
        self.api_key = QWEN_API_KEY
        self.base_url = QWEN_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def chat(
        self, 
        system_prompt: str, 
        user_message: str, 
        model: str = "qwen-plus",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Send a chat message to Qwen API"""
        if not self.api_key:
            return "⚠️ AI Service: API key not configured. Please set QWEN_API_KEY in .env"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            print(f"HTTP error: {e}")
            return f"Error: {str(e)}"
        except Exception as e:
            print(f"Error: {e}")
            return f"Error: {str(e)}"
    
    async def summarize_session(self, messages: List[dict]) -> str:
        """Summarize a chat session"""
        system_prompt = "Tu es un assistant qui résume les conversations de manière concise."
        messages_text = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages[-10:]])
        user_message = f"Résume cette conversation en 3-5 points clés:\n{messages_text}"
        
        return await self.chat(system_prompt, user_message, model="qwen-plus")