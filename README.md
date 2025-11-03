# Weekly Budget Summary Agent (Telex Integration)

A FastAPI-based agent that integrates with [Telex AI](https://telex.im/) to track weekly budgets, add income/expenses, and generate a weekly summary. Uses Redis for session storage and supports webhooks.

---

## Features

- Add income and expenses via natural text commands.
- Generate weekly budget summaries.
- Handles multi-command messages in a single request.
- Fully compatible with Telex JSON-RPC validation.
- Webhook notifications for push updates.
- Persistent session storage via Redis.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/zeehy123/weekly-budget-agent.git
cd weekly-budget-agent
```
2. Create a virtual Environment and install dependencies
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate.ps1    # Windows
pip install -r requirements.txt

3. Configure environment variables
PORT=5004
REDIS_URL=redis://localhost:6379/0

=======================================================================
Running Locally
Start FastAPI server:
uvicorn main:app --reload --host 0.0.0.0 --port 5004

Health check:
curl http://localhost:5004/health
# {"status": "healthy", "agent": "weekly_budget"}
=================================================================================
Usage
Send JSON-RPC requests to /a2a/budget. Example:
{
  "jsonrpc": "2.0",
  "id": "user-1",
  "method": "message/send",
  "params": {
    "message": {
      "kind": "message",
      "role": "user",
      "parts": [
        {"kind": "text", "text": "Add expense 50 for groceries"},
        {"kind": "text", "text": "Show summary"}
      ]
    },
    "configuration": {
      "pushNotificationConfig": {
        "url": "https://your-webhook.url",
        "token": "YOUR_TOKEN",
        "authentication": {"schemes":["Bearer"]}
      }
    }
  }
}
=====================================================================================
Tech Stack

FastAPI – HTTP server for handling Telex requests
Python 3.11+
Redis – Session storage for users and transactions
HTTPX – Webhook notifications
Pydantic – JSON-RPC request validation


