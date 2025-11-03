from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from models.a2a import JSONRPCRequest
from agents.budget_agents import BudgetAgent
from contextlib import asynccontextmanager
from enum import Enum
from datetime import datetime, timezone
import uuid
import os
import traceback
import json

load_dotenv()

budget_agent: BudgetAgent | None = None


class A2AErrorCode(Enum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


def create_error_response(request_id: str | None, code: A2AErrorCode, message: str, data=None):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code.value,
            "message": message,
            "data": data or {},
        },
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget_agent
    budget_agent = BudgetAgent()
    print("🚀 BudgetAgent initialized")
    yield
    print("🔌 Shutting down BudgetAgent")


app = FastAPI(
    title="Weekly Budget Summary Agent",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/a2a/budget")
async def a2a_endpoint(request: Request):
    print("✅ /a2a/budget endpoint hit")

    # Parse incoming JSON
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=create_error_response(None, A2AErrorCode.PARSE_ERROR, "Invalid JSON", {"detail": str(e)}),
        )

    # Normalize Telex input
    try:
        if "params" in body:
            params = body["params"]

            # Flatten nested parts
            if "messages" in params:
                for msg in params["messages"]:
                    if "parts" in msg and isinstance(msg["parts"], list):
                        for i, part in enumerate(msg["parts"]):
                            if isinstance(part, list) and len(part) == 1 and isinstance(part[0], dict):
                                msg["parts"][i] = part[0]

            # Convert single 'message' to 'messages' list
            if "message" in params and "messages" not in params:
                params["messages"] = [params["message"]]

    except Exception as e:
        print("⚠️ Normalization warning:", e)

    # Validate JSON-RPC
    try:
        rpc_request = JSONRPCRequest(**body)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=create_error_response(body.get("id"), A2AErrorCode.INVALID_REQUEST, "Invalid Request", {"details": str(e)}),
        )

    rpc_id = body.get("id")

    try:
        params = rpc_request.params
        messages = getattr(params, "messages", None)
        if not messages and hasattr(params, "message"):
            messages = [params.message]

        context_id = getattr(params, "contextId", "default-context")
        task_id = getattr(params, "taskId", str(uuid.uuid4()))
        config = getattr(params, "configuration", None)

        print(f"🧭 Context ID: {context_id}")
        print(f"🪶 Messages: {messages}")

        # Process via BudgetAgent
        result_obj = await budget_agent.process_messages(messages, context_id=context_id, task_id=task_id, config=config)

        # Extract summary text
        summary_text = None
        if hasattr(result_obj, "status") and hasattr(result_obj.status, "message"):
            message = result_obj.status.message
            if message.parts and len(message.parts) > 0:
                summary_text = getattr(message.parts[0], "text", None)
        elif isinstance(result_obj, dict):
            summary_text = result_obj.get("summary") or result_obj.get("message")
        else:
            summary_text = str(result_obj)

        summary_text = summary_text or "Summary generated successfully."

        # Build JSON-RPC response
        task_uuid = task_id or str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        final_response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "id": task_uuid,
                "contextId": context_id,
                "status": {
                    "state": "completed",
                    "timestamp": timestamp,
                    "message": {
                        "messageId": str(uuid.uuid4()),
                        "role": "agent",
                        "parts": [{"kind": "text", "text": summary_text}],
                        "kind": "message",
                        "taskId": task_uuid,
                    },
                },
                "artifacts": [],
                "history": messages + [result_obj.status.message],
                "kind": "task",
            },
            "error": None,
        }

        return JSONResponse(content=final_response)

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=create_error_response(rpc_id, A2AErrorCode.INTERNAL_ERROR, "Internal error", {"detail": str(e)}),
        )


@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "weekly_budget"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 5004))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
