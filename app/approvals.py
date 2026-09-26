import sqlite3
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent.parent / "approvals.db"

REFUND_APPROVAL_THRESHOLD_EGP = 200.0


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                amount_egp REAL NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)


def create_approval(order_id: str, amount_egp: float, reason: str) -> str:
    approval_id = str(uuid.uuid4())[:8]
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO approvals (id, order_id, amount_egp, reason, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (approval_id, order_id, amount_egp, reason, datetime.now(timezone.utc).isoformat()),
        )
    logger.info("Approval created: id=%s order=%s amount=%.2f", approval_id, order_id, amount_egp)
    return approval_id


def list_pending() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


def get_approval(approval_id: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        return dict(row) if row else None


def set_status(approval_id: str, status: str):
    with _get_conn() as conn:
        conn.execute("UPDATE approvals SET status = ? WHERE id = ?", (status, approval_id))
    logger.info("Approval %s marked %s", approval_id, status)


init_db()