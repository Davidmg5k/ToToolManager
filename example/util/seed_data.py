"""Seed script: inserts 10+ records into every table of the production DB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import uuid4
from random import choice, randint, uniform

from app import engine, init_db
from app.model import (
    User, Order, Product, PaymentRecord,
    NotificationRecord,
)
from app.types.order import OrderStatus
from app.types.payment import PaymentMethod, PaymentStatus
from app.types.notification import NotificationChannel, NotificationStatus

from sqlmodel import Session, select

FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Ethan",
    "Fiona", "George", "Hannah", "Ivan", "Julia",
    "Kevin", "Laura", "Mike", "Nina", "Oscar",
]
LAST_NAMES = [
    "Smith", "Johnson", "Brown", "Davis", "Miller",
    "Wilson", "Moore", "Taylor", "Anderson", "Thomas",
]
PRODUCTS = [
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

CHANNELS = list(NotificationChannel)
METHODS = list(PaymentMethod)
PAY_STATUSES = list(PaymentStatus)
NOTIF_STATUSES = list(NotificationStatus)
ORDER_STATUSES = list(OrderStatus)


def _rand_email(first, last):
    domain = choice(["example.com", "test.org", "mail.dev", "inbox.io"])
    return f"{first.lower()}.{last.lower()}@{domain}"


def seed():
    init_db()
    with Session(engine) as session:
        # 1. USERS
        existing_users = session.exec(select(User)).all()
        user_count = len(existing_users)
        print(f"Existing users: {user_count}")
        new_users = []
        needed = max(0, 12 - user_count)
        for i in range(needed):
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            last = LAST_NAMES[i % len(LAST_NAMES)]
            u = User(user_id=uuid4(), user_name=f"{first} {last}",
                     email=_rand_email(first, last), password=f"pass_{first.lower()}_{i}")
            new_users.append(u)
        if new_users:
            session.add_all(new_users)
            session.commit()
            print(f"  Inserted {len(new_users)} users")

        all_users = list(session.exec(select(User)).all())
        user_ids = [u.user_id for u in all_users]

        # 2. PRODUCTS
        existing_products = session.exec(select(Product)).all()
        product_count = len(existing_products)
        print(f"Existing products: {product_count}")
        new_products = []
        needed = max(0, 12 - product_count)
        for i in range(needed):
            name, desc, sku, price, stock = PRODUCTS[i % len(PRODUCTS)]
            p = Product(product_id=uuid4(), name=f"{name} #{i+1}", description=desc,
                        sku=f"{sku}-{i+1:03d}", price=round(price * uniform(0.8, 1.2), 2),
                        stock=stock + randint(-10, 30))
            new_products.append(p)
        if new_products:
            session.add_all(new_products)
            session.commit()
            print(f"  Inserted {len(new_products)} products")

        # 3. ORDERS
        existing_orders = session.exec(select(Order)).all()
        order_count = len(existing_orders)
        print(f"Existing orders: {order_count}")
        new_orders = []
        needed = max(0, 12 - order_count)
        product_names = [p[0] for p in PRODUCTS]
        for i in range(needed):
            o = Order(order_id=uuid4(), user_id=choice(user_ids),
                      product_name=choice(product_names), quantity=randint(1, 5),
                      unit_price=round(uniform(10.0, 1500.0), 2),
                      status=choice(ORDER_STATUSES))
            new_orders.append(o)
        if new_orders:
            session.add_all(new_orders)
            session.commit()
            print(f"  Inserted {len(new_orders)} orders")

        all_orders = list(session.exec(select(Order)).all())
        order_ids = [o.order_id for o in all_orders]

        # 4. PAYMENT RECORDS
        existing_payments = session.exec(select(PaymentRecord)).all()
        payment_count = len(existing_payments)
        print(f"Existing payment records: {payment_count}")
        new_payments = []
        needed = max(0, 12 - payment_count)
        for i in range(needed):
            pr = PaymentRecord(payment_id=uuid4(), order_id=choice(order_ids),
                               amount=round(uniform(10.0, 2000.0), 2),
                               method=choice(METHODS), currency=choice(["USD", "EUR", "GBP"]),
                               status=choice(PAY_STATUSES))
            new_payments.append(pr)
        if new_payments:
            session.add_all(new_payments)
            session.commit()
            print(f"  Inserted {len(new_payments)} payment records")

        # 5. NOTIFICATION RECORDS
        existing_notifs = session.exec(select(NotificationRecord)).all()
        notif_count = len(existing_notifs)
        print(f"Existing notification records: {notif_count}")
        new_notifs = []
        needed = max(0, 12 - notif_count)
        subjects = [
            "Order Confirmed", "Shipping Update", "Payment Received",
            "Account Created", "Password Reset", "Promo Offer",
            "New Feature", "System Maintenance", "Welcome!", "Feedback Request",
        ]
        for i in range(needed):
            uid = choice(user_ids)
            nr = NotificationRecord(notification_id=uuid4(), user_id=uid,
                                    channel=choice(CHANNELS), subject=choice(subjects),
                                    body=f"This is notification body #{i+1}.",
                                    recipient=f"user_{uid.hex[:8]}@example.com",
                                    status=choice(NOTIF_STATUSES))
            new_notifs.append(nr)
        if new_notifs:
            session.add_all(new_notifs)
            session.commit()
            print(f"  Inserted {len(new_notifs)} notification records")

        # Summary
        print("\n--- Final counts ---")
        for label, model in [
            ("users", User), ("products", Product), ("orders", Order),
            ("payments", PaymentRecord), ("notifications", NotificationRecord),
        ]:
            count = len(session.exec(select(model)).all())
            print(f"  {label:20s}: {count}")


if __name__ == "__main__":
    seed()
