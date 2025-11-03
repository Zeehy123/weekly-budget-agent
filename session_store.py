import redis.asyncio as redis
import os
import json
from typing import Any, Dict

class SessionStore:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        redis_password = os.getenv("REDIS_PASSWORD")

        if not redis_url:
            raise ValueError("Missing REDIS_URL in environment variables.")

        # ✅ Create Redis connection (disable SSL certificate verification for Leapcell)
        self.redis = redis.from_url(
            redis_url,
            decode_responses=True,   # ensures values are returned as str
            ssl_cert_reqs=None,      # disable SSL verification for Leapcell
            password=redis_password,
        )

    async def append_transaction(self, user_id: str, transaction: Dict[str, Any]):
        """Append a transaction to user's transaction list."""
        key = f"user:{user_id}:transactions"

        current = await self.redis.get(key)
        data = json.loads(current) if current else {"transactions": []}
        data["transactions"].append(transaction)

        await self.redis.set(key, json.dumps(data))
        print(f"💾 Transaction saved for {user_id}: {transaction}")

    async def load_user_data(self, user_id: str) -> Dict[str, Any]:
        """Load all user data (transactions)."""
        key = f"user:{user_id}:transactions"
        current = await self.redis.get(key)
        return json.loads(current) if current else {"transactions": []}

    async def get_value(self, key: str):
        """Safely get a single Redis value."""
        val = await self.redis.get(key)
        return val  # ✅ already decoded (no .decode())

    async def set_value(self, key: str, value: str, ex: int = 3600):
        """Set a value with an optional expiry."""
        await self.redis.set(key, value, ex=ex)
