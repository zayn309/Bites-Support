import uuid
import time
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.graph import graph
from app.logging_config import setup_logging
from app.approvals import list_pending, get_approval, set_status
from app.tools import repo

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Bites Support")


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    logger.info("session=%s user_message=%s", session_id, req.message)
    config = {"configurable": {"thread_id": session_id}}

    start = time.perf_counter()
    try:
        result = graph.invoke({"messages": [("user", req.message)]}, config=config)
        reply = result["messages"][-1].content
        elapsed = time.perf_counter() - start
        logger.info("session=%s reply=%s latency_ms=%.0f", session_id, reply, elapsed * 1000)
    except Exception:
        logger.exception("session=%s agent invocation failed", session_id)
        reply = "Sorry, something went wrong. Please try again."

    return ChatResponse(session_id=session_id, reply=reply)


@app.get("/history/{session_id}")
def get_history(session_id: str):
    config = {"configurable": {"thread_id": session_id}}
    state = graph.get_state(config)
    messages = state.values.get("messages", []) if state and state.values else []

    history = []
    for m in messages:
        role = "user" if m.type == "human" else "bot"
        if m.content:  # skip empty tool-call-only messages
            history.append({"role": role, "content": m.content})
    return {"messages": history}


@app.get("/admin/pending")
def get_pending():
    return {"pending": list_pending()}


@app.post("/admin/approve/{approval_id}")
def approve(approval_id: str):
    approval = get_approval(approval_id)
    if not approval or approval["status"] != "pending":
        return {"error": "Not found or already resolved"}

    order = repo.get(approval["order_id"])
    if order and not order.refunded:
        order.refunded = True
        logger.info("Refund executed after approval: order=%s amount=%.2f", approval["order_id"], approval["amount_egp"])

    set_status(approval_id, "approved")
    return {"status": "approved"}


@app.post("/admin/reject/{approval_id}")
def reject(approval_id: str):
    set_status(approval_id, "rejected")
    return {"status": "rejected"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")