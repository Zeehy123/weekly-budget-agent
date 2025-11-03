from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional
import httpx
from session_store import SessionStore
from models.a2a import (
    A2AMessage, TaskResult, TaskStatus, MessagePart, MessageConfiguration
)

class BudgetAgent:
    def __init__(self):
        # Initialize Redis-backed store
        self.store = SessionStore()

    async def _get_or_create_user_id(self, context_id: str, message: A2AMessage) -> str:
        """Ensure every context gets a stable user_id, stored in Redis."""
        user_id = None

        # Try extract from message metadata
        if hasattr(message, "sender") and getattr(message.sender, "id", None):
            user_id = str(message.sender.id)
        elif hasattr(message, "user") and getattr(message.user, "id", None):
            user_id = str(message.user.id)

        # If not provided by Telex, check Redis
        if not user_id:
            user_id = await self.store.get_value(f"user:context:{context_id}")
            if user_id:
                print(f"♻️ Reusing stored user_id {user_id} for context {context_id}")
            else:
                user_id = f"auto_user_{uuid4()}"
                await self.store.set_value(f"user:context:{context_id}", user_id)
                print(f"🆕 Created new user_id {user_id} for context {context_id}")

        return user_id

    async def process_messages(self, messages, context_id=None, task_id=None, config: Optional[MessageConfiguration]=None):
        print("📩 Received message dump")
        if not messages:
            raise ValueError("No messages")

        context_id = context_id or str(uuid4())
        task_id = task_id or str(uuid4())

        message = messages[-1]
        user_id = await self._get_or_create_user_id(context_id, message)
        print(f"🧭 User identified as {user_id}")
        print(f"🔑 Redis key used: {user_id}")

        # Parse text content
        user_text = ""
        for part in message.parts:
            if part.kind == "text" and part.text:
                user_text = part.text.lower().strip()
                break

        # Default help text
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
            print("🟢 Detected 'summary' command, generating summary...")
            response_text = await self._generate_weekly_summary(user_id)

        # Build and send response
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
        print(f"🧭 Generating weekly summary for user {user_id}")
        data = await self.store.load_user_data(user_id)
        print(f"📦 Loaded data from Redis: {data}")

        transactions = data.get("transactions", [])
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = [t for t in transactions if datetime.fromisoformat(t["date"]) > week_ago]

        if not recent:
            print("❌ No recent transactions found this week.")
            return "No transactions recorded this week yet."

        income = sum(t["amount"] for t in recent if t["type"] == "income")
        expense = sum(t["amount"] for t in recent if t["type"] == "expense")
        balance = income - expense

        summary = f"📅 Weekly Summary → Income ₦{int(income)}, Expenses ₦{int(expense)}, Balance ₦{int(balance)} 💪"
        print(f"🪵 Weekly summary for {user_id}: {summary}")
        return summary

    def _extract_number(self, text: str) -> int:
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', text.replace(",", ""))
        return int(float(match.group(1))) if match else 0
