import logging
from typing import Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, MessagesState
from langchain.agents import create_agent
from app.helper import clean_history
from app.llm import get_llm
from app.tools import ORDER_TOOLS, BILLING_TOOLS, FAQ_TOOLS
from app.prompts import SUPERVISOR, ORDER_AGENT, BILLING_AGENT, FAQ_AGENT
from app.logging_config import setup_logging

import sqlite3
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver


load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

llm = get_llm()

order_agent = create_agent(llm, ORDER_TOOLS, system_prompt=ORDER_AGENT)
billing_agent = create_agent(llm, BILLING_TOOLS, system_prompt=BILLING_AGENT)
faq_agent = create_agent(llm, FAQ_TOOLS, system_prompt=FAQ_AGENT)

DB_PATH = Path(__file__).parent.parent / "checkpoints.sqlite"
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
checkpointer = SqliteSaver(conn)

def supervisor_node(state: MessagesState) -> dict:
    recent = state["messages"][-4:]  
    decision = llm.invoke([("system", SUPERVISOR)] + recent)
    route = decision.content.strip().lower()
    logger.info("Supervisor routed to: %s", route)
    if route not in ("order", "billing", "faq"):
        logger.warning("Unrecognized route '%s', defaulting to faq", route)
        route = "faq"
    return {"route": route}

class RoutedState(MessagesState):
    route: str

def order_node(state: RoutedState) -> dict:
    clean = clean_history(state["messages"])
    result = order_agent.invoke({"messages": clean})
    reply = result["messages"][-1]
    return {"messages": [reply]}


def billing_node(state: RoutedState) -> dict:
    clean = clean_history(state["messages"])
    result = billing_agent.invoke({"messages": clean})
    reply = result["messages"][-1]
    return {"messages": [reply]}


def faq_node(state: RoutedState) -> dict:
    clean = clean_history(state["messages"])
    result = faq_agent.invoke({"messages": clean})
    reply = result["messages"][-1]
    return {"messages": [reply]}


def route_selector(state: RoutedState) -> Literal["order", "billing", "faq"]:
    return state["route"]


builder = StateGraph(RoutedState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("order", order_node)
builder.add_node("billing", billing_node)
builder.add_node("faq", faq_node)

builder.set_entry_point("supervisor")
builder.add_conditional_edges("supervisor", route_selector, {
    "order": "order",
    "billing": "billing",
    "faq": "faq",
})
builder.add_edge("order", END)
builder.add_edge("billing", END)
builder.add_edge("faq", END)

graph = builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    import uuid
    thread_id = str(uuid.uuid4())  # one conversation per CLI run
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        q = input("You: ")
        logger.info("User message: %s", q)
        try:
            result = graph.invoke({"messages": [("user", q)]}, config=config)
            reply = result["messages"][-1].content
        except Exception:
            logger.exception("Graph invocation failed")
            reply = "Sorry, something went wrong. Please try again."
        print("Bot:", reply)