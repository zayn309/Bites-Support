
import contextvars
 
current_customer_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_customer_id", default=None
)
 