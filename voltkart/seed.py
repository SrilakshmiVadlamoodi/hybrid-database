"""
seed.py — populates VoltKart Postgres tables with ~300 rows of realistic dummy data.

Run: python seed.py
Requires schema.sql to already be applied.
"""
import os
import random
from datetime import timedelta

import psycopg2
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
fake = Faker("en_IN")
random.seed(42)

CONN_PARAMS = dict(
    host=os.getenv("PGHOST", "localhost"),
    port=os.getenv("PGPORT", "5432"),
    user=os.getenv("PGUSER", "postgres"),
    password=os.getenv("PGPASSWORD", ""),
    dbname=os.getenv("PGDATABASE", "voltkart"),
)

N_CUSTOMERS = 60
N_PRODUCTS = 40
N_ORDERS = 100
N_TICKETS = 50  # order_items + payments derive from N_ORDERS, bringing total rows to ~300+

CATEGORIES = {
    "Smartphone": ["Pinnacle", "Zenova", "Kairo", "Verto"],
    "Laptop": ["Nexbook", "Coretech", "Aeropad"],
    "Headphones": ["SonicWave", "BassLine", "AeroSound"],
    "Smartwatch": ["PulseFit", "Chronos", "Orbita"],
    "Speaker": ["BoomBox", "EchoTune"],
    "Charger": ["VoltEdge", "PowerLoop"],
}

TICKET_CATEGORIES = ["DELIVERY", "PRODUCT_DEFECT", "PAYMENT", "RETURN", "GENERAL"]
TICKET_SUBJECTS = {
    "DELIVERY": ["Order not delivered", "Delivery delayed", "Wrong address delivery"],
    "PRODUCT_DEFECT": ["Product not working", "Screen damaged on arrival", "Battery draining fast"],
    "PAYMENT": ["Payment deducted but order failed", "Refund not received", "Double charge on card"],
    "RETURN": ["Want to return product", "Exchange request", "Return pickup not scheduled"],
    "GENERAL": ["Warranty query", "Product usage help", "Invoice request"],
}
PAYMENT_METHODS = ["CARD", "UPI", "NETBANKING", "COD", "WALLET"]
ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED"]


def seed_customers(cur):
    ids = []
    for _ in range(N_CUSTOMERS):
        cur.execute(
            """INSERT INTO customers (full_name, email, phone, city, state, pincode, signup_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING customer_id""",
            (
                fake.name(),
                fake.unique.email(),
                fake.msisdn()[:10],
                fake.city(),
                fake.state(),
                fake.postcode(),
                fake.date_between(start_date="-2y", end_date="today"),
            ),
        )
        ids.append(cur.fetchone()[0])
    return ids


def seed_products(cur):
    ids = []
    for _ in range(N_PRODUCTS):
        category = random.choice(list(CATEGORIES.keys()))
        brand = random.choice(CATEGORIES[category])
        price = round(random.uniform(499, 89999), 2)
        cur.execute(
            """INSERT INTO products (product_name, category, brand, price, stock, warranty_months)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING product_id""",
            (
                f"{brand} {category} {fake.word().capitalize()}",
                category,
                brand,
                price,
                random.randint(0, 200),
                random.choice([6, 12, 24]),
            ),
        )
        ids.append(cur.fetchone()[0])
    return ids


def seed_orders_items_payments(cur, customer_ids, product_ids):
    order_ids = []
    for _ in range(N_ORDERS):
        customer_id = random.choice(customer_ids)
        status = random.choice(ORDER_STATUSES)
        order_date = fake.date_time_between(start_date="-1y", end_date="now")
        cur.execute(
            """INSERT INTO orders (customer_id, order_date, status, total_amount, shipping_city)
               VALUES (%s, %s, %s, 0, %s) RETURNING order_id""",
            (customer_id, order_date, status, fake.city()),
        )
        order_id = cur.fetchone()[0]
        order_ids.append(order_id)

        # 1-4 line items per order, no duplicate products in the same order
        items_products = random.sample(product_ids, k=random.randint(1, 4))
        total = 0
        for product_id in items_products:
            cur.execute("SELECT price FROM products WHERE product_id = %s", (product_id,))
            unit_price = cur.fetchone()[0]
            quantity = random.randint(1, 3)
            cur.execute(
                """INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                   VALUES (%s, %s, %s, %s)""",
                (order_id, product_id, quantity, unit_price),
            )
            total += float(unit_price) * quantity

        cur.execute("UPDATE orders SET total_amount = %s WHERE order_id = %s", (round(total, 2), order_id))

        # One payment per order
        pay_status = "SUCCESS" if status in ("SHIPPED", "DELIVERED") else random.choice(["PENDING", "SUCCESS", "FAILED"])
        cur.execute(
            """INSERT INTO payments (order_id, payment_method, amount, payment_status, paid_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                order_id,
                random.choice(PAYMENT_METHODS),
                round(total, 2),
                pay_status,
                order_date + timedelta(minutes=random.randint(1, 60)),
            ),
        )
    return order_ids


def seed_support_tickets(cur, customer_ids, order_ids):
    for _ in range(N_TICKETS):
        category = random.choice(TICKET_CATEGORIES)
        cur.execute(
            """INSERT INTO support_tickets (customer_id, order_id, subject, category, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                random.choice(customer_ids),
                random.choice(order_ids) if random.random() < 0.8 else None,
                random.choice(TICKET_SUBJECTS[category]),
                category,
                random.choice(["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]),
                fake.date_time_between(start_date="-1y", end_date="now"),
            ),
        )


def main():
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            print("Seeding customers...")
            customer_ids = seed_customers(cur)
            print("Seeding products...")
            product_ids = seed_products(cur)
            print("Seeding orders, order_items, payments...")
            order_ids = seed_orders_items_payments(cur, customer_ids, product_ids)
            print("Seeding support_tickets...")
            seed_support_tickets(cur, customer_ids, order_ids)
        conn.commit()

        with conn.cursor() as cur:
            for table in ["customers", "products", "orders", "order_items", "payments", "support_tickets"]:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"{table}: {cur.fetchone()[0]} rows")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
