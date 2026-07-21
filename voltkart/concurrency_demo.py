"""
concurrency_demo.py — demonstrates the lost-update anomaly on products.stock
using two concurrent sessions (threads + psycopg2), then shows the fix using
two-phase locking (SELECT ... FOR UPDATE, which Postgres uses to implement 2PL
for row-level locks under READ COMMITTED).

Scenario: two customers simultaneously try to buy the last few units of the
same product. Each session reads current stock, then writes stock - quantity.
Without locking, both reads can happen before either write, causing one sale
to silently overwrite the other's stock decrement ("lost update").

Run: python concurrency_demo.py
"""
import os
import threading
import time

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

DEMO_PRODUCT_ID = 1
STARTING_STOCK = 10
PURCHASE_QTY = 3  # two sessions each buy 3 -> correct final stock = 10 - 3 - 3 = 4


def reset_stock():
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("UPDATE products SET stock = %s WHERE product_id = %s", (STARTING_STOCK, DEMO_PRODUCT_ID))
    conn.close()


def get_stock():
    conn = psycopg2.connect(**CONN_PARAMS)
    with conn.cursor() as cur:
        cur.execute("SELECT stock FROM products WHERE product_id = %s", (DEMO_PRODUCT_ID,))
        stock = cur.fetchone()[0]
    conn.close()
    return stock


def buy_without_lock(session_name, barrier):
    """Read-then-write with NO row lock: classic lost-update race."""
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stock FROM products WHERE product_id = %s", (DEMO_PRODUCT_ID,))
            current_stock = cur.fetchone()[0]
            print(f"[{session_name}] read stock = {current_stock}")

            # Force both sessions to have read stale data before either writes,
            # to reliably reproduce the race instead of leaving it to chance timing.
            barrier.wait()
            time.sleep(0.2)

            new_stock = current_stock - PURCHASE_QTY
            cur.execute("UPDATE products SET stock = %s WHERE product_id = %s", (new_stock, DEMO_PRODUCT_ID))
            print(f"[{session_name}] wrote stock = {new_stock}")
        conn.commit()
    finally:
        conn.close()


def buy_with_lock(session_name, start_gate):
    """Read-then-write WITH SELECT ... FOR UPDATE: 2PL row lock prevents the race.

    FOR UPDATE acquires an exclusive row lock at read time (growing phase) and
    holds it until COMMIT (shrinking phase) — this is Postgres's mechanism for
    two-phase locking on a single row. The second session BLOCKS inside the
    SELECT itself until the first session commits, so it always reads the
    up-to-date value. (No barrier.wait() here after the SELECT — the whole
    point is that a locked-out session can't reach that line until the lock
    is released, so a 2-party barrier there would deadlock.)
    """
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            start_gate.wait()  # only used to start both threads at roughly the same time
            print(f"[{session_name}] requesting row lock...")
            cur.execute("SELECT stock FROM products WHERE product_id = %s FOR UPDATE", (DEMO_PRODUCT_ID,))
            current_stock = cur.fetchone()[0]
            print(f"[{session_name}] acquired lock, read stock = {current_stock}")

            time.sleep(0.2)  # simulate think time while holding the lock

            new_stock = current_stock - PURCHASE_QTY
            cur.execute("UPDATE products SET stock = %s WHERE product_id = %s", (new_stock, DEMO_PRODUCT_ID))
            print(f"[{session_name}] wrote stock = {new_stock}")
        conn.commit()  # releases the lock (end of 2PL shrinking phase)
    finally:
        conn.close()


def run_demo(buy_fn, title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    reset_stock()
    print(f"Starting stock = {STARTING_STOCK}")

    barrier = threading.Barrier(2)
    t1 = threading.Thread(target=buy_fn, args=("Session-A", barrier))
    t2 = threading.Thread(target=buy_fn, args=("Session-B", barrier))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    final_stock = get_stock()
    expected = STARTING_STOCK - 2 * PURCHASE_QTY
    print(f"Final stock = {final_stock} (expected {expected})")
    if final_stock == expected:
        print("RESULT: correct — no lost update.")
    else:
        print("RESULT: LOST UPDATE detected — one session's decrement was overwritten.")


if __name__ == "__main__":
    run_demo(buy_without_lock, "DEMO 1: WITHOUT locking (lost-update anomaly)")
    run_demo(buy_with_lock, "DEMO 2: WITH 2PL row lock (SELECT ... FOR UPDATE)")
