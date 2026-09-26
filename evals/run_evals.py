"""
NOTE: if BILLING_AGENT still asks clarifying questions for the "wrong items"
case despite order ID + amount + reason being given, tighten the prompt with:
"If the customer has already given the order ID, amount, and a reason (even
a general one like 'wrong order' or 'missing item'), proceed to check
eligibility and call issue_refund directly — do not ask for further detail
before acting."

Lightweight eval harness for Bites Support.

Checks two things per test case:
1. Did the supervisor route to the expected specialist?
2. Did the expected tool(s) actually get called (captured via logging)?

Not a replacement for real test infrastructure — this is meant to catch
regressions quickly when a prompt or tool docstring changes, by re-running
a fixed set of representative messages instead of manually re-testing by hand.
"""

import logging
import sys
from pathlib import Path
import uuid
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.graph import graph  # noqa: E402
from app.approvals import list_pending  # noqa: E402


class ToolCallCapture(logging.Handler):
    """Collects 'TOOL CALLED: x(...)' log lines emitted during one graph.invoke() call."""

    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    def emit(self, record):
        msg = record.getMessage()
        if "TOOL CALLED:" in msg:
            tool_name = msg.split("TOOL CALLED:")[1].strip().split("(")[0]
            self.calls.append(tool_name)

    def reset(self):
        self.calls = []


capture = ToolCallCapture()
logging.getLogger("app.tools").addHandler(capture)
logging.getLogger("app.rag").addHandler(capture)


TEST_CASES = [
    {
        "name": "order status - Arabic",
        "message": "فين الأوردر بتاعي رقم 1001؟",
        "expected_route": "order",
        "expected_tools": ["get_order_status"],
    },
    {
        "name": "order status - English",
        "message": "what's the status of order 1002",
        "expected_route": "order",
        "expected_tools": ["get_order_status"],
    },
    {
        "name": "order not found",
        "message": "where is order 9999",
        "expected_route": "order",
        "expected_tools": ["get_order_status"],
        "expected_keywords": ["9999"],
    },
    {
        "name": "small refund - auto-approved (order 1001, 35 min late, qualifies)",
        "message": "refund me 50 EGP for order 1001, it arrived 35 minutes late",
        "expected_route": "billing",
        "expected_tools": ["issue_refund"],
    },
    {
        "name": "large refund - needs approval (order 1004, wrong items, full detail given)",
        "message": (
            "Order 1004 arrived with the wrong dish entirely, not what I ordered. "
            "Please refund the full 300 EGP for order 1004."
        ),
        "expected_route": "billing",
        "expected_tools": ["issue_refund"],
        "expect_pending_approval": True,
    },
    {
        "name": "refund correctly denied - order not late enough",
        "message": "refund me 50 EGP for order 1003, it was late",
        "expected_route": "billing",
        "expected_tools": ["search_faq"],
        "expected_keywords": ["30"],
    },
    {
        "name": "faq - promo codes",
        "message": "can I combine a promo code with free delivery?",
        "expected_route": "faq",
        "expected_tools": ["search_faq"],
    },
    {
        "name": "faq - allergies, Arabic",
        "message": "عندي حساسية من الفول، هل ينفع أطلب؟",
        "expected_route": "faq",
        "expected_tools": ["search_faq"],
    },
    {
        "name": "mixed intent - refund priority (order id included)",
        "message": "order 1001 is late and I want a 50 EGP refund",
        "expected_route": "billing",
        "expected_tools": ["issue_refund"],
    },
    {
        "name": "out of scope",
        "message": "what's the weather like today?",
        "expected_route": "faq",
        "expected_tools": [],
    },
]



def run_case(case: dict) -> dict:
    capture.reset()
    pending_before = {a["id"] for a in list_pending()}

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}  # fresh, isolated thread per test
    result = graph.invoke({"messages": [("user", case["message"])]}, config=config)

    reply = result["messages"][-1].content
    
    actual_route = result.get("route", "?")
    actual_tools = capture.calls.copy()

    pending_after = {a["id"] for a in list_pending()}
    new_approval_created = len(pending_after - pending_before) > 0

    route_ok = actual_route == case["expected_route"]
    tools_ok = all(t in actual_tools for t in case.get("expected_tools", []))
    keywords_ok = all(
        kw.lower() in reply.lower() for kw in case.get("expected_keywords", [])
    )
    approval_ok = (
        new_approval_created if case.get("expect_pending_approval") else True
    )

    passed = route_ok and tools_ok and keywords_ok and approval_ok

    return {
        "name": case["name"],
        "passed": passed,
        "route_ok": route_ok,
        "tools_ok": tools_ok,
        "keywords_ok": keywords_ok,
        "approval_ok": approval_ok,
        "expected_route": case["expected_route"],
        "actual_route": actual_route,
        "expected_tools": case.get("expected_tools", []),
        "actual_tools": actual_tools,
        "reply": reply,
    }


def main():
    logging.getLogger("app.tools").setLevel(logging.INFO)
    logging.getLogger("app.rag").setLevel(logging.INFO)

    results = [run_case(c) for c in TEST_CASES]

    print("\n" + "=" * 70)
    print("BITES SUPPORT — EVAL RESULTS")
    print("=" * 70)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n[{status}] {r['name']}")
        if not r["route_ok"]:
            print(f"    route: expected '{r['expected_route']}', got '{r['actual_route']}'")
        if not r["tools_ok"]:
            print(f"    tools: expected {r['expected_tools']}, got {r['actual_tools']}")
        if not r["keywords_ok"]:
            print(f"    reply missing expected keyword(s)")
        if not r["approval_ok"]:
            print(f"    expected a new pending approval to be created, but none was found")
        if not r["passed"]:
            print(f"    reply: {r['reply'][:150]}")

    passed = sum(r["passed"] for r in results)
    total = len(results)
    print("\n" + "-" * 70)
    print(f"{passed}/{total} passed ({passed / total * 100:.0f}%)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()