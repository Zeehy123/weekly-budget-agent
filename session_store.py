import os
import redis
import json
import urllib.parse
from typing import Any, Dict

class SessionStore:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        redis_username = os.getenv("REDIS_USERNAME")  # optional, default 'default'
        redis_password = os.getenv("REDIS_PASSWORD")

        if not redis_url:
            raise ValueError("Missing REDIS_URL in environment variables.")

        # URL-encode password
        if redis_password:
            redis_password = urllib.parse.quote_plus(redis_password)

        self.redis = redis.Redis.from_url(
            url=redis_url,
            username=redis_username or "default",
            password=redis_password,
            ssl=True,
            ssl_cert_reqs=None,  # skip certificate verification for Leapcell Redis
            decode_responses=True
        )

    async def append_transaction(self, user_id: str, transaction: Dict[str, Any]):
        """Append a transaction to user's transaction list."""
        key = f"user:{user_id}:transactions"
        current = self.redis.get(key)
        data = json.loads(current) if current else {"transactions": []}
        data["transactions"].append(transaction)
        self.redis.set(key, json.dumps(data))
        print(f"💾 Transaction saved for {user_id}: {transaction}")

    async def load_user_data(self, user_id: str) -> Dict[str, Any]:
        """Load all user data (transactions)."""
        key = f"user:{user_id}:transactions"
        current = self.redis.get(key)
        return json.loads(current) if current else {"transactions": []}
