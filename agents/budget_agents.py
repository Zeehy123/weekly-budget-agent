import json
from datetime import datetime, timedelta
from uuid import uuid4
from models.a2a import (
    A2AMessage, TaskResult, TaskStatus, Artifact,
    MessagePart, MessageConfiguration
)

DATA_FILE = "budget_data.json"

class BudgetAgent:
    def __init__(self):
        self.load_data()

    def load_data(self):
        try:
            with open(DATA_FILE, "r") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {"users": {}}

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    async def process_messages(self, messages, context_id=None, task_id=None, config=None):
        context_id = context_id or str(uuid4())
        task_id = task_id or str(uuid4())

        message = messages[-1]
        user_text = ""
        for part in message.parts:
            if part.kind == "text":
                user_text = part.text.lower().strip()

        response_text = "I didn’t understand that. You can say things like:\n" \
                        "- 'Add expense 500 for groceries'\n" \
                        "- 'Add income 2000 salary'\n" \
                        "- 'Show summary'"

        user_id = context_id  # simple assumption

        if "add expense" in user_text:
            amount = self._extract_number(user_text)
            self._add_transaction(user_id, "expense", amount)
            response_text = f"🧾 Added expense of ₦{amount}"

        elif "add income" in user_text:
            amount = self._extract_number(user_text)
            self._add_transaction(user_id, "income", amount)
            response_text = f"💰 Added income of ₦{amount}"

        elif "summary" in user_text:
            response_text = self._generate_weekly_summary(user_id)

        response_message = A2AMessage(
            role="agent",
            parts=[MessagePart(kind="text", text=response_text)],
            taskId=task_id
        )

        return TaskResult(
            id=task_id,
            contextId=context_id,
            status=TaskStatus(state="completed", message=response_message),
            artifacts=[],
            history=messages + [response_message]
        )

    def _add_transaction(self, user_id, type_, amount):
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {"transactions": []}

        self.data["users"][user_id]["transactions"].append({
            "type": type_,
            "amount": amount,
            "date": datetime.utcnow().isoformat()
        })
        self.save_data()

    def _extract_number(self, text):
        import re
        match = re.search(r'\d+', text)
        return int(match.group()) if match else 0

    def _generate_weekly_summary(self, user_id):
        user_data = self.data["users"].get(user_id, {"transactions": []})
        week_ago = datetime.utcnow() - timedelta(days=7)
        transactions = [
            t for t in user_data["transactions"]
            if datetime.fromisoformat(t["date"]) > week_ago
        ]

        income = sum(t["amount"] for t in transactions if t["type"] == "income")
        expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
        balance = income - expense

        summary = (
        "**📅 Weekly Budget Summary**\n"
        f"- **Income:** ₦{income}\n"
        f"- **Expenses:** ₦{expense}\n"
        f"- **Balance:** ₦{balance}\n"
        "Keep up the good work! 💪"
    )


        return summary
