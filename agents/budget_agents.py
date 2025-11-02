# budget_agent.py
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional
import httpx
import os
from session_store import SessionStore
from models.a2a import (
    A2AMessage, TaskResult, TaskStatus, Artifact,
    MessagePart, MessageConfiguration
)

class BudgetAgent:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("Missing REDIS_URL in environment variables.")
        self.store = SessionStore()

    async def send_webhook_notification(self, webhook_url: str, result: TaskResult, auth: Optional[dict] = None):
        headers = {"Content-Type": "application/json"}
        if auth and isinstance(auth, dict):
            token = auth.get("credentials") or auth.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(webhook_url, json=result.model_dump(), headers=headers)
            except Exception as e:
                print("❌ Webhook push failed:", e)

    def _stable_user_id_from_message(self, message: A2AMessage, context_id: str) -> str:
        md = message.metadata or {}
        for key in ("sender", "user", "from"):
            candidate = md.get(key) if isinstance(md, dict) else None
            if candidate:
                if isinstance(candidate, dict):
                    uid = candidate.get("id") or candidate.get("userId") or candidate.get("user_id")
                    if uid:
                        return str(uid)
                else:
                    return str(candidate)
        return context_id

    async def process_messages(self, messages, context_id=None, task_id=None, config: Optional[MessageConfiguration]=None):
        print("📩 Received message dump")
        if not messages:
            raise ValueError("No messages")

        context_id = context_id or str(uuid4())
        task_id = task_id or str(uuid4())

        message = messages[-1]
        user_id = self._stable_user_id_from_message(message, context_id)

        user_text = ""
        for part in message.parts:
            if part.kind == "text" and part.text:
                user_text = part.text.lower().strip()
                break

        response_text = (
            "I didn’t understand that. Try:\n"
            "- 'Add expense 500 groceries'\n"
            "- 'Add income 2000 salary'\n"
            "- 'Show summary'"
        )

        if "add expense" in user_text:
            amount = self._extract_number(user_text)
            if amount > 0:
                await self._add_transaction(user_id, "expense", amount)
                response_text = f"🧾 Added expense of ₦{amount}"
            else:
                response_text = "Could not detect amount. Try: 'Add expense 500 for gas'."

        elif "add income" in user_text:
            amount = self._extract_number(user_text)
            if amount > 0:
                await self._add_transaction(user_id, "income", amount)
                response_text = f"💰 Added income of ₦{amount}"
            else:
                response_text = "Could not detect amount. Try: 'Add income 2000 salary'."

        elif "summary" in user_text:
            response_text = await self._generate_weekly_summary(user_id)

        response_message = A2AMessage(
            kind="message",
            role="agent",
            parts=[MessagePart(kind="text", text=response_text.strip())],
            taskId=task_id
        )

        result = TaskResult(
            id=task_id,
            contextId=context_id,
            status=TaskStatus(state="completed", message=response_message),
            artifacts=[],
            history=messages + [response_message]
        )

        if config and config.pushNotificationConfig and config.pushNotificationConfig.url:
            await self.send_webhook_notification(config.pushNotificationConfig.url, result, auth=config.pushNotificationConfig.authentication)

        return result

    async def _add_transaction(self, user_id: str, type_: str, amount: float):
        tx = {
            "type": type_,
            "amount": float(amount),
            "date": datetime.utcnow().isoformat()
        }
        await self.store.append_transaction(user_id, tx)
        print(f"💾 Saved to Redis: {type_} ₦{amount}")

    async def _generate_weekly_summary(self, user_id: str) -> str:
        data = await self.store.load_user_data(user_id)
        transactions = data.get("transactions", [])
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = [
            t for t in transactions
            if datetime.fromisoformat(t["date"]) > week_ago
        ]

        if not recent:
            return "No transactions recorded this week yet."

        income = sum(t["amount"] for t in recent if t["type"] == "income")
        expense = sum(t["amount"] for t in recent if t["type"] == "expense")
        balance = income - expense

        return f"📅 Weekly Summary → Income ₦{int(income)}, Expenses ₦{int(expense)}, Balance ₦{int(balance)} 💪"

    def _extract_number(self, text: str) -> int:
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', text.replace(",", ""))
        return int(float(match.group(1))) if match else 0
