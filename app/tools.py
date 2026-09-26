import logging
from dataclasses import dataclass

from langchain_core.tools import tool
from app.approvals import create_approval, REFUND_APPROVAL_THRESHOLD_EGP

logger = logging.getLogger(__name__)


@dataclass
class Order:
    id: str
    customer_id: str
    restaurant: str
    items: list[str]
    total_egp: float
    status: str  # preparing | on_the_way | delivered | cancelled
    minutes_late: int = 0
    driver: str | None = None
    refunded: bool = False


class OrderRepo:
    """In-memory for now. Swappable for a real database later without
    changing any tool function signatures — only this class's internals would change."""

    def __init__(self):
        self._orders: dict[str, Order] = {
            "1001": Order("1001", "c1", "Koshary El Tahrir", ["Large Koshary", "Coke"], 85.0,
                          "on_the_way", minutes_late=35, driver="Ahmed"),
            "1002": Order("1002", "c1", "Zooba", ["Taameya Sandwich x2"], 120.0, "delivered"),
            "1003": Order("1003", "c2", "Cook Door", ["Chicken Shawarma", "Fries"], 210.0,
                          "preparing", minutes_late=10),
            "1004": Order("1004", "c2", "Sobhy Kaber", ["Mixed Grill"], 480.0, "delivered"),
        }

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def list_for_customer(self, customer_id: str) -> list[Order]:
        return [o for o in self._orders.values() if o.customer_id == customer_id]


repo = OrderRepo()


@tool
def get_order_status(order_id: str) -> str:
    """Get full order details by ID: restaurant, items, total price in EGP,
    delivery status, delay in minutes, and driver name."""
    logger.info("TOOL CALLED: get_order_status(order_id=%s)", order_id)
    o = repo.get(order_id)
    if not o:
        logger.warning("Order not found: %s", order_id)
        return f"No order found with ID {order_id}."
    return (f"Order {o.id} from {o.restaurant}: {', '.join(o.items)} "
            f"({o.total_egp} EGP). Status: {o.status}. "
            f"Late by {o.minutes_late} min. Driver: {o.driver or 'not assigned yet'}.")


@tool
def list_customer_orders(customer_id: str) -> str:
    """List all orders for a customer ID, including restaurant, status, and total price for each."""
    logger.info("TOOL CALLED: list_customer_orders(customer_id=%s)", customer_id)
    orders = repo.list_for_customer(customer_id)
    if not orders:
        return "No orders found for this customer."
    return "\n".join(f"{o.id}: {o.restaurant}, {o.status}, {o.total_egp} EGP" for o in orders)


@tool
def issue_refund(order_id: str, amount_egp: float, reason: str) -> str:
    """Issue a refund for an order. Amount must not exceed the order's actual total price.
    Refunds above the approval threshold are automatically queued for manager review instead
    of executing immediately — call this normally regardless of amount, the tool handles the logic."""
    logger.info("TOOL CALLED: issue_refund(order_id=%s, amount=%s)", order_id, amount_egp)
    o = repo.get(order_id)
    if not o:
        return f"No order found with ID {order_id}."
    if o.refunded:
        return f"Order {order_id} was already refunded."
    if amount_egp > o.total_egp:
        return f"Refund exceeds order total of {o.total_egp} EGP."

    if amount_egp > REFUND_APPROVAL_THRESHOLD_EGP:
        approval_id = create_approval(order_id, amount_egp, reason)
        return (f"This refund ({amount_egp} EGP) is above the {REFUND_APPROVAL_THRESHOLD_EGP} EGP "
                f"self-service limit, so I've sent it for manager review (reference: {approval_id}). "
                f"You'll be refunded once it's approved, usually within a few hours.")

    o.refunded = True
    return f"Refunded {amount_egp} EGP for order {order_id}. Reason: {reason}."


from app.rag import search_faq  # noqa: E402

ORDER_TOOLS = [get_order_status, list_customer_orders, search_faq]
BILLING_TOOLS = [issue_refund, get_order_status, search_faq]
FAQ_TOOLS = [search_faq]