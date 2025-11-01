

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from models.a2a import JSONRPCRequest, JSONRPCResponse
from agents.budget_agents import BudgetAgent

from contextlib import asynccontextmanager
import os

load_dotenv()

budget_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget_agent
    budget_agent = BudgetAgent()
    yield

app = FastAPI(
    title="Weekly Budget Summary Agent",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/a2a/budget")
async def a2a_endpoint(request: Request):
    try:
        body = await request.json()
        rpc_request = JSONRPCRequest(**body)

        if rpc_request.method == "message/send":
            messages = [rpc_request.params.message]
            config = rpc_request.params.configuration
        else:
            messages = rpc_request.params.messages
            config = None

        result = await budget_agent.process_messages(messages, config=config)
        return JSONRPCResponse(id=rpc_request.id, result=result).model_dump()

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": "Internal error", "data": str(e)},
            },
        )

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "weekly_budget"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 5001))
    uvicorn.run(app, host="0.0.0.0", port=port)