from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from models.a2a import JSONRPCRequest, A2AMessage
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
        "error": {"code": code.value, "message": message, "data": data or {}}
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget_agent
    budget_agent = BudgetAgent()
    print("🚀 BudgetAgent initialized")
    yield
    print("🔌 Shutting down BudgetAgent")

app = FastAPI(title="Weekly Budget Summary Agent", version="1.0.0", lifespan=lifespan)

# Flatten nested parts
def flatten_parts(parts):
    flat = []
    for part in parts:
        if isinstance(part, list):
            flat.extend(flatten_parts(part))
        elif isinstance(part, dict):
            flat.append(part)
    return flat

# Serialize messages to Telex-safe JSON
def serialize_message(message: A2AMessage):
    return {
        "kind": getattr(message, "kind", "message"),
        "role": getattr(message, "role", "agent"),
        "messageId": getattr(message, "messageId", str(uuid.uuid4())),
        "taskId": getattr(message, "taskId", str(uuid.uuid4())),
        "parts": [
            {
                "kind": getattr(part, "kind", "text"),
                "text": getattr(part, "text", ""),
                "data": getattr(part, "data", {}) if isinstance(getattr(part, "data", {}), dict) else {},
                "file_url": getattr(part, "file_url", None),
            }
            for part in getattr(message, "parts", [])
        ],
        "metadata": getattr(message, "metadata", {}) or {}
    }

@app.post("/a2a/budget")
async def a2a_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=create_error_response(None, A2AErrorCode.PARSE_ERROR, "Invalid JSON", {"detail": str(e)})
        )

    # Normalize input
    try:
        if "params" in body:
            params = body["params"]
            if "message" in params and "messages" not in params:
                params["messages"] = [params["message"]]
            if "messages" in params:
                for msg in params["messages"]:
                    if "parts" in msg and isinstance(msg["parts"], list):
                        msg["parts"] = flatten_parts(msg["parts"])
    except Exception as e:
        print("⚠️ Normalization warning:", e)

    try:
        rpc_request = JSONRPCRequest(**body)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=create_error_response(body.get("id"), A2AErrorCode.INVALID_REQUEST, "Invalid Request", {"details": str(e)})
        )

    rpc_id = body.get("id")

    try:
        params = rpc_request.params
        messages = getattr(params, "messages", [getattr(params, "message", None)])
        messages = [m for m in messages if m is not None]

        context_id = getattr(params, "contextId", "default-context")
        task_id = getattr(params, "taskId", str(uuid.uuid4()))
        config = getattr(params, "configuration", None)

        print(f"🧭 Context ID: {context_id}")
        print(f"🪶 Messages: {messages}")

        # Process via BudgetAgent
        result_obj = await budget_agent.process_messages(messages, context_id=context_id, task_id=task_id, config=config)

        task_uuid = task_id or str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        response_result = {
            "id": task_uuid,
            "contextId": context_id,
            "status": {"state": "completed", "timestamp": timestamp, "message": serialize_message(result_obj.status.message)},
            "artifacts": [],
            "history": [serialize_message(m) for m in messages] + [serialize_message(result_obj.status.message)],
            "kind": "task",
        }

        final_response = {"jsonrpc": "2.0", "id": rpc_id, "result": response_result, "error": None}

        print("📤 Sending final Telex JSON-RPC response:")
        print(json.dumps(final_response, indent=2))
        return JSONResponse(content=final_response)

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=create_error_response(rpc_id, A2AErrorCode.INTERNAL_ERROR, "Internal error", {"detail": str(e)})
        )

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "weekly_budget"}
