"""
Database setup for Bites Support order data.

Run directly to (re)create the schema and seed mock data:
    python -m app.db --force
"""

import argparse
import json
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "orders.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id   TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    order_id              TEXT PRIMARY KEY,
    customer_id           TEXT NOT NULL,
    restaurant_name       TEXT NOT NULL,
    items_json            TEXT NOT NULL,
    total_price_egp       REAL NOT NULL,
    driver_name           TEXT,
    status                TEXT NOT NULL CHECK (status IN ('preparing', 'on_the_way', 'delivered', 'cancelled')),
    delivery_started_at   TEXT,
    estimated_delivery_at TEXT,
    delivered_at          TEXT,
    refunded              INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
"""

SEED_CUSTOMERS = [
    ("c1", "sara.mostafa@example.com"),
    ("c2", "omar.hassan@example.com"),
]

# minutes offsets are relative to 'now' at seed time, so demo data always
# looks freshly late/on-time no matter when you run this
SEED_ORDERS = [
    {
        "order_id": "1001",
        "customer_id": "c1",
        "restaurant_name": "Koshary El Tahrir",
        "items": [{"name": "Large Koshary", "qty": 1}, {"name": "Coke", "qty": 1}],
        "total_price_egp": 85.0,
        "driver_name": "Ahmed",
        "status": "on_the_way",
        "delivery_started_minutes_ago": 65,   # started 65 min ago
        "estimated_duration_minutes": 30,     # expected to take 30 min -> 35 min late
    },
    {
        "order_id": "1002",
        "customer_id": "c1",
        "restaurant_name": "Zooba",
        "items": [{"name": "Taameya Sandwich", "qty": 2}],
        "total_price_egp": 120.0,
        "driver_name": "Mahmoud",
        "status": "delivered",
        "delivery_started_minutes_ago": 90,
        "estimated_duration_minutes": 35,
        "delivered_minutes_ago": 55,           # arrived at 35 min mark, right on estimate
    },
    {
        "order_id": "1003",
        "customer_id": "c2",
        "restaurant_name": "Cook Door",
        "items": [{"name": "Chicken Shawarma", "qty": 1}, {"name": "Fries", "qty": 1}],
        "total_price_egp": 210.0,
        "driver_name": None,
        "status": "preparing",
        "delivery_started_minutes_ago": None,
        "estimated_duration_minutes": 35,
    },
    {
        "order_id": "1004",
        "customer_id": "c2",
        "restaurant_name": "Sobhy Kaber",
        "items": [{"name": "Mixed Grill", "qty": 1}],
        "total_price_egp": 480.0,
        "driver_name": "Karim",
        "status": "delivered",
        "delivery_started_minutes_ago": 120,
        "estimated_duration_minutes": 40,
        "delivered_minutes_ago": 80,
    },
]


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def build_db(force: bool = False):
    if force and DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("Removed existing %s", DB_PATH)

    conn = _get_conn()
    conn.executescript(SCHEMA)

    for customer_id, email in SEED_CUSTOMERS:
        conn.execute(
            "INSERT OR IGNORE INTO customers (customer_id, email) VALUES (?, ?)",
            (customer_id, email),
        )

    for o in SEED_ORDERS:
        started = None
        estimated = None
        delivered = None

        if o["delivery_started_minutes_ago"] is not None:
            started = f"datetime('now', '-{o['delivery_started_minutes_ago']} minutes')"
            estimated = f"datetime('now', '-{o['delivery_started_minutes_ago'] - o['estimated_duration_minutes']} minutes')"
        if o.get("delivered_minutes_ago") is not None:
            delivered = f"datetime('now', '-{o['delivered_minutes_ago']} minutes')"

        conn.execute(
            f"""
            INSERT OR IGNORE INTO orders
                (order_id, customer_id, restaurant_name, items_json, total_price_egp,
                 driver_name, status, delivery_started_at, estimated_delivery_at, delivered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, {started or 'NULL'}, {estimated or 'NULL'}, {delivered or 'NULL'})
            """,
            (
                o["order_id"], o["customer_id"], o["restaurant_name"],
                json.dumps(o["items"]), o["total_price_egp"], o["driver_name"], o["status"],
            ),
        )

    conn.commit()
    conn.close()
    logger.info("Database ready at %s", DB_PATH)


def parse_args():
    parser = argparse.ArgumentParser(description="Build/seed the Bites Support orders database.")
    parser.add_argument("--force", action="store_true", help="Wipe and recreate from scratch.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_db(force=args.force)