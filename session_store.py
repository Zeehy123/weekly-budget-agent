# session_store.py
import redis.asyncio as redis
from typing import Optional, Dict, Any
import json

class SessionStore:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def load_user_data(self, user_id: str) -> Dict[str, Any]:
        key = f"budget:user:{user_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return {"transactions": []}

    async def save_user_data(self, user_id: str, data: Dict[str, Any]):
        key = f"budget:user:{user_id}"
        await self.redis.set(key, json.dumps(data), ex=7 * 24 * 3600)  # 7-day expiry

    async def append_transaction(self, user_id: str, transaction: Dict[str, Any]):
        data = await self.load_user_data(user_id)
        data["transactions"].append(transaction)
        await self.save_user_data(user_id, data)
