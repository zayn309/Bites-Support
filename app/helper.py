from langchain_core.messages import HumanMessage, AIMessage


def clean_history(messages):
    """Strip tool-call artifacts so handing off to a different specialist
    (with a different tool set) doesn't break the provider's validation."""
    cleaned = []
    for m in messages:
        if isinstance(m, HumanMessage):
            cleaned.append(m)
        elif isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            cleaned.append(m)
        # ToolMessage and tool-calling AIMessage are intentionally dropped —
        # they belong to whichever specialist made that call, not the shared history.
    return cleaned