from datetime import datetime, timedelta
from uuid import uuid4
from typing import Optional
import httpx
from html import unescape
import re
from session_store import SessionStore
from models.a2a import A2AMessage, TaskResult, TaskStatus, MessagePart, MessageConfiguration

class BudgetAgent:
    def __init__(self):
        # Initialize Redis-backed store
        self.store = SessionStore()

    # -------------------------------
    # Webhook notification support
    # -------------------------------
    async def send_webhook_notification(self, url: str, payload: dict, auth: dict | None = None):
        try:
            headers = {}
            if auth and "schemes" in auth and "Bearer" in auth["schemes"] and "token" in auth:
                headers["Authorization"] = f'Bearer {auth["token"]}'
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, headers=headers)
            print(f"🔔 Push notification sent to {url}")
        except Exception as e:
            print(f"⚠️ Failed to send webhook: {e}")

    # -------------------------------
    # Get or create stable user_id
    # -------------------------------
    async def _get_or_create_user_id(self, context_id: str, message: A2AMessage) -> str:
        user_id = None
        if hasattr(message, "sender") and getattr(message.sender, "id", None):
            user_id = str(message.sender.id)
        elif hasattr(message, "user") and getattr(message.user, "id", None):
            user_id = str(message.user.id)

        if not user_id:
            user_id = await self.store.get_value(f"user:context:{context_id}")
            if user_id:
                print(f"♻️ Reusing stored user_id {user_id} for context {context_id}")
            else:
                user_id = f"auto_user_{uuid4()}"
                await self.store.set_value(f"user:context:{context_id}", user_id)
                print(f"🆕 Created new user_id {user_id} for context {context_id}")

        return user_id

    # -------------------------------
    # Process incoming messages
    # -------------------------------
    async def process_messages(self, messages, context_id=None, task_id=None, config: Optional[MessageConfiguration] = None):
        if not messages:
            raise ValueError("No messages")

        context_id = context_id or str(uuid4())
        task_id = task_id or str(uuid4())
        message = messages[-1]
        user_id = await self._get_or_create_user_id(context_id, message)
        print(f"🧭 User identified as {user_id}")

        # Combine all text parts
        user_text_raw = ""
        for part in message.parts:
            if part.kind == "text" and part.text:
                user_text_raw += " " + part.text

        # Clean text: remove HTML tags, unescape, normalize spaces
        user_text_clean = re.sub(r"<[^>]*>", " ", user_text_raw)
        user_text_clean = unescape(user_text_clean)
        user_text_clean = " ".join(user_text_clean.split()).lower()
        print(f"📝 Cleaned user text: {user_text_clean}")

        # Split commands by common separators (optional: could add ; or newline)
        commands = user_text_clean.split("summary")  # crude split to handle multiple summaries
        response_text = "I didn’t understand that. Try:\n- 'Add expense 500 groceries'\n- 'Add income 2000 salary'\n- 'Show summary'"

        for cmd in commands:
            cmd = cmd.strip()
            if "add expense" in cmd:
                amount = self._extract_number(cmd)
                if amount > 0:
                    await self._add_transaction(user_id, "expense", amount)
                    response_text = f"🧾 Added expense of ₦{amount}"
            elif "add income" in cmd:
                amount = self._extract_number(cmd)
                if amount > 0:
                    await self._add_transaction(user_id, "income", amount)
                    response_text = f"💰 Added income of ₦{amount}"
            elif cmd:  # if non-empty, treat as summary command
                response_text = await self._generate_weekly_summary(user_id)

        # Build response message
        response_message = A2AMessage(
            kind="message",
            role="agent",
            parts=[MessagePart(kind="text", text=response_text.strip(), data={})],
            taskId=task_id
        )

        result = TaskResult(
            id=task_id,
            contextId=context_id,
            status=TaskStatus(state="completed", message=response_message),
            artifacts=[],
            history=messages + [response_message]
        )

        # Send webhook if configured
        if config and config.pushNotificationConfig and config.pushNotificationConfig.url:
            await self.send_webhook_notification(
                config.pushNotificationConfig.url,
                payload=result.__dict__,
                auth=config.pushNotificationConfig.authentication
            )

        return result

    # -------------------------------
    # Add transaction to Redis
    # -------------------------------
    async def _add_transaction(self, user_id: str, type_: str, amount: float):
        tx = {"type": type_, "amount": float(amount), "date": datetime.utcnow().isoformat()}
        await self.store.append_transaction(user_id, tx)
        print(f"💾 Saved to Redis: {type_} ₦{amount}")

    # -------------------------------
    # Generate weekly summary
    # -------------------------------
    async def _generate_weekly_summary(self, user_id: str) -> str:
        print(f"🧭 Generating weekly summary for user {user_id}")
        data = await self.store.load_user_data(user_id)
        transactions = data.get("transactions", [])
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent = [t for t in transactions if datetime.fromisoformat(t["date"]) > week_ago]

        if not recent:
            return "No transactions recorded this week yet."

        income = sum(t["amount"] for t in recent if t["type"] == "income")
        expense = sum(t["amount"] for t in recent if t["type"] == "expense")
        balance = income - expense

        summary = f"📅 Weekly Summary → Income ₦{int(income)}, Expenses ₦{int(expense)}, Balance ₦{int(balance)} 💪"
        print(f"🪵 Weekly summary for {user_id}: {summary}")
        return summary

    # -------------------------------
    # Extract numeric value from text
    # -------------------------------
    def _extract_number(self, text: str) -> int:
        match = re.search(r'(\d+(?:\.\d+)?)', text.replace(",", ""))
        return int(float(match.group(1))) if match else 0
