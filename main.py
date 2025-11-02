# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from models.a2a import JSONRPCRequest, JSONRPCResponse
from agents.budget_agents import BudgetAgent
from contextlib import asynccontextmanager
import os
from enum import Enum

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
            "data": data or {}
        }
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget_agent
    budget_agent = BudgetAgent()
    print("🚀 BudgetAgent initialized")
    yield
    print("🔌 Shutting down BudgetAgent")

app = FastAPI(title="Weekly Budget Summary Agent", version="1.0.0", lifespan=lifespan)

@app.post("/a2a/budget")
async def a2a_endpoint(request: Request):
    print("✅ /a2a/budget endpoint hit")
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(status_code=400, content=create_error_response(None, A2AErrorCode.PARSE_ERROR, "Invalid JSON", {"detail": str(e)}))

    # Validate JSON-RPC shape
    try:
        rpc_request = JSONRPCRequest(**body)
    except Exception as e:
        print("❌ Request validation failed:", e)
        return JSONResponse(status_code=400, content=create_error_response(body.get("id"), A2AErrorCode.INVALID_REQUEST, "Invalid Request", {"details": str(e)}))

    try:
        # Support both message/send and execute
        if rpc_request.method == "message/send":
            params = rpc_request.params
            messages = [params.message]
            config = params.configuration
            context_id = getattr(params.message, "metadata", None) and getattr(params.message.metadata, "get", lambda k, d=None: None)("contextId") or None
            task_id = params.message.taskId or None
        else:
            # execute
            params = rpc_request.params
            messages = params.messages
            config = None
            context_id = params.contextId
            task_id = params.taskId

        # Pass messages into the agent
        result: JSONRPCResponse = await budget_agent.process_messages(messages, context_id=context_id, task_id=task_id, config=config)
        # result is TaskResult pydantic model from agent
        return JSONRPCResponse(id=rpc_request.id, result=result).model_dump()

    except Exception as e:
        print("❌ Internal error:", e)
        return JSONResponse(status_code=500, content=create_error_response(rpc_request.id, A2AErrorCode.INTERNAL_ERROR, "Internal error", {"detail": str(e)}))

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "weekly_budget"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5001))
    print(f"Starting UVicorn on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
