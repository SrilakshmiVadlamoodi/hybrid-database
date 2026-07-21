"""
indexing_demo.py — shows EXPLAIN ANALYZE before/after adding a B-tree index.

Demonstrates two lookup queries that are common in VoltKart's app:
  1. "Find all orders for a customer" (orders.customer_id)
  2. "Find all support tickets for a customer" (support_tickets.customer_id)

Run: python indexing_demo.py
"""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

CONN_PARAMS = dict(
    host=os.getenv("PGHOST", "localhost"),
    port=os.getenv("PGPORT", "5432"),
    user=os.getenv("PGUSER", "postgres"),
    password=os.getenv("PGPASSWORD", ""),
    dbname=os.getenv("PGDATABASE", "voltkart"),
)

QUERIES = [
    ("Orders for a customer", "SELECT * FROM orders WHERE customer_id = 5;"),
    ("Support tickets for a customer", "SELECT * FROM support_tickets WHERE customer_id = 5;"),
]

INDEXES = [
    ("idx_orders_customer_id", "orders", "customer_id"),
    ("idx_support_tickets_customer_id", "support_tickets", "customer_id"),
]


def explain(cur, label, sql):
    # Disable seq scan bias from cache warmup by running twice, keep the 2nd (warm) result
    cur.execute(f"EXPLAIN ANALYZE {sql}")
    plan = "\n".join(row[0] for row in cur.fetchall())
    print(f"--- {label} ---")
    print(plan)
    print()


def drop_indexes(cur):
    for name, _, _ in INDEXES:
        cur.execute(f"DROP INDEX IF EXISTS {name};")


def create_indexes(cur):
    for name, table, col in INDEXES:
        cur.execute(f"CREATE INDEX {name} ON {table}({col});")


def main():
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = True
    with conn.cursor() as cur:
        print("=" * 60)
        print("BEFORE INDEX (sequential scan expected)")
        print("=" * 60)
        drop_indexes(cur)
        for label, sql in QUERIES:
            explain(cur, label, sql)

        print("=" * 60)
        print("AFTER INDEX (planner's natural choice)")
        print("=" * 60)
        create_indexes(cur)
        cur.execute("ANALYZE orders; ANALYZE support_tickets;")
        for label, sql in QUERIES:
            explain(cur, label, sql)

        # On a table this small (~100-300 rows), the planner correctly decides a
        # sequential scan is cheaper than an index scan (one disk page vs. index
        # traversal + heap lookup) — this is realistic, not a bug. To actually see
        # the B-tree index scan in the plan, we force it off and re-run.
        print("=" * 60)
        print("AFTER INDEX, WITH SEQ SCAN DISABLED (forces B-tree index scan)")
        print("=" * 60)
        cur.execute("SET enable_seqscan = off;")
        for label, sql in QUERIES:
            explain(cur, label, sql)
        cur.execute("SET enable_seqscan = on;")

    conn.close()


if __name__ == "__main__":
    main()
