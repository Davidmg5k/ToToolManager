"""Standalone seed script using only stdlib sqlite3 - no app imports needed."""

import sqlite3
from pathlib import Path
import uuid
import random

DB_PATH = str(Path(__file__).parent.parent / "data" / "app.db")

FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan",
    "Fiona", "George", "Hannah", "Ivan", "Julia",
    "Kevin", "Laura", "Mike", "Nina", "Oscar",
]
LAST_NAMES = [
    "Smith", "Johnson", "Brown", "Davis", "Miller",
    "Wilson", "Moore", "Taylor", "Anderson", "Thomas",
]
PRODUCTS_DATA = [
    ("Laptop Pro 15", "High-performance laptop", "LAP-001", 1299.99, 25),
    ("Wireless Mouse", "Ergonomic wireless mouse", "MOU-002", 29.99, 150),
    ("Mechanical Keyboard", "RGB mechanical keyboard", "KEY-003", 89.99, 80),
    ("4K Monitor", "27-inch 4K display", "MON-004", 449.99, 30),
    ("USB-C Hub", "7-in-1 USB-C hub", "HUB-005", 49.99, 200),
    ("Webcam HD", "1080p webcam with mic", "CAM-006", 79.99, 100),
    ("Noise-Cancel Headphones", "Over-ear ANC headphones", "HEA-007", 199.99, 60),
    ("Portable SSD 1TB", "External solid-state drive", "SSD-008", 109.99, 120),
    ("Desk Lamp LED", "Adjustable LED desk lamp", "LMP-009", 34.99, 90),
    ("Ergonomic Chair", "Adjustable office chair", "CHR-010", 599.99, 15),
    ("Graphics Tablet", "Drawing tablet with pen", "TAB-011", 249.99, 40),
    ("Ring Light", "18-inch ring light", "LIT-012", 59.99, 70),
]

CHANNELS = ["email", "sms", "push"]
METHODS = ["credit_card", "debit_card", "bank_transfer", "cash"]
PAY_STATUSES = ["pending", "completed", "failed", "refunded"]
NOTIF_STATUSES = ["pending", "sent", "delivered", "failed"]
ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]


def rand_email(first, last):
    domain = random.choice(["example.com", "test.org", "mail.dev", "inbox.io"])
    return f"{first.lower()}.{last.lower()}@{domain}"


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    # Check existing counts
    tables = {
        "user": "user_id",
        "product": "product_id",
        "order": "order_id",
        "paymentrecord": "payment_id",
        "notificationrecord": "notification_id",
    }
    for table, pk in tables.items():
        count = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:25s}: {count} existing")

    # 1. USERS
    existing_users = [r[0] for r in c.execute("SELECT user_id FROM user").fetchall()]
    needed = max(0, 12 - len(existing_users))
    new_user_ids = []
    for i in range(needed):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[i % len(LAST_NAMES)]
        uid = str(uuid.uuid4())
        new_user_ids.append(uid)
        c.execute("INSERT INTO user (user_id, user_name, email, password) VALUES (?, ?, ?, ?)",
                  (uid, f"{first} {last}", rand_email(first, last), f"pass_{first.lower()}_{i}"))
    if new_user_ids:
        conn.commit()
        print(f"  Inserted {len(new_user_ids)} users")

    all_user_ids = [r[0] for r in c.execute("SELECT user_id FROM user").fetchall()]

    # 2. PRODUCTS
    existing_products = c.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    needed = max(0, 12 - existing_products)
    for i in range(needed):
        name, desc, sku, price, stock = PRODUCTS_DATA[i % len(PRODUCTS_DATA)]
        pid = str(uuid.uuid4())
        adj_price = round(price * random.uniform(0.8, 1.2), 2)
        adj_stock = stock + random.randint(-10, 30)
        c.execute("INSERT INTO product (product_id, name, description, sku, price, stock) VALUES (?, ?, ?, ?, ?, ?)",
                  (pid, f"{name} #{i+1}", desc, f"{sku}-{i+1:03d}", adj_price, adj_stock))
    if needed > 0:
        conn.commit()
        print(f"  Inserted {needed} products")

    # 3. ORDERS
    existing_orders = c.execute("SELECT COUNT(*) FROM order").fetchone()[0]
    needed = max(0, 12 - existing_orders)
    product_names = [p[0] for p in PRODUCTS_DATA]
    new_order_ids = []
    for i in range(needed):
        oid = str(uuid.uuid4())
        new_order_ids.append(oid)
        c.execute(
            "INSERT INTO [order] (order_id, user_id, product_name, quantity, unit_price, status) VALUES (?, ?, ?, ?, ?, ?)",
            (oid, random.choice(all_user_ids), random.choice(product_names),
             random.randint(1, 5), round(random.uniform(10.0, 1500.0), 2), random.choice(ORDER_STATUSES))
        )
    if new_order_ids:
        conn.commit()
        print(f"  Inserted {len(new_order_ids)} orders")

    all_order_ids = [r[0] for r in c.execute("SELECT order_id FROM [order]").fetchall()]

    # 4. PAYMENT RECORDS
    existing_payments = c.execute("SELECT COUNT(*) FROM paymentrecord").fetchone()[0]
    needed = max(0, 12 - existing_payments)
    for i in range(needed):
        payid = str(uuid.uuid4())
        c.execute(
            "INSERT INTO paymentrecord (payment_id, order_id, amount, method, currency, status) VALUES (?, ?, ?, ?, ?, ?)",
            (payid, random.choice(all_order_ids), round(random.uniform(10.0, 2000.0), 2),
             random.choice(METHODS), random.choice(["USD", "EUR", "GBP"]), random.choice(PAY_STATUSES))
        )
    if needed > 0:
        conn.commit()
        print(f"  Inserted {needed} payment records")

    # 5. NOTIFICATION RECORDS
    existing_notifs = c.execute("SELECT COUNT(*) FROM notificationrecord").fetchone()[0]
    needed = max(0, 12 - existing_notifs)
    subjects = [
        "Order Confirmed", "Shipping Update", "Payment Received",
        "Account Created", "Password Reset", "Promo Offer",
        "New Feature", "System Maintenance", "Welcome!", "Feedback Request",
    ]
    for i in range(needed):
        nid = str(uuid.uuid4())
        uid = random.choice(all_user_ids)
        c.execute(
            "INSERT INTO notificationrecord (notification_id, user_id, channel, subject, body, recipient, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nid, uid, random.choice(CHANNELS), random.choice(subjects),
             f"This is notification body #{i+1}. Please review the details.",
             f"user_{uid[:8]}@example.com", random.choice(NOTIF_STATUSES))
        )
    if needed > 0:
        conn.commit()
        print(f"  Inserted {needed} notification records")

    # Final summary
    print("\n--- Final counts ---")
    for table in ["user", "product", "order", "paymentrecord", "notificationrecord"]:
        count = c.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        print(f"  {table:25s}: {count}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    seed()
