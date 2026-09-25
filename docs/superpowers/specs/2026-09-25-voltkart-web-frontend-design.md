# VoltKart Web Frontend — Design

## Purpose

Add a minimal, server-rendered web frontend to the existing VoltKart hybrid-database
learning project, so the existing PostgreSQL schema and 2PL concurrency logic
(`concurrency_demo.py`) can be exercised through a UI instead of only via scripts.
No schema changes, no ORM, no authentication.

## Stack

- FastAPI + Jinja2 templates, plain HTML/CSS (no JS framework)
- Raw SQL via `psycopg2` (no ORM), reusing the connection pattern already used by
  `concurrency_demo.py` / `seed.py` (`python-dotenv` reads `voltkart/.env`)
- Entry point: `uvicorn main:app --reload`, port 8000
- All new code lives inside `voltkart/`

## File layout

```
voltkart/
  main.py               FastAPI app; mounts routers, static files, Jinja2Templates
  db.py                 psycopg2 SimpleConnectionPool + get_conn() context manager
  cart.py               in-memory cart store: {customer_id: {product_id: qty}}
  routes/
    __init__.py
    catalog.py           GET /  (product list + ?category= filter)
                          GET /products/{product_id}  (detail)
    cart.py               POST /cart/add
                          GET /cart
                          POST /cart/checkout   (the 2PL order-placement transaction)
    orders.py             GET /orders?customer_id=
    support.py             GET /support?customer_id=
                          POST /support/new
    admin.py               GET /admin  (read-only tables: customers, products,
                                         orders, payments)
  templates/
    base.html              nav + customer_id dropdown, shared across pages
    catalog.html, product_detail.html, cart.html, orders.html,
    support.html, admin.html
  static/
    style.css             plain CSS
```

No changes to `schema.sql`, `seed.py`, `concurrency_demo.py`, `mongo_demo.py`,
`indexing_demo.py`.

## Data access

`db.py` creates one `psycopg2.pool.SimpleConnectionPool` at import time using the
same env vars as the existing scripts (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`,
`PGDATABASE`). Routes borrow a connection via a context manager, run raw SQL with
parameterized queries (`%s` placeholders — never string-interpolated SQL), and return
it to the pool. No query builder, no ORM.

## Cart

Since the schema has no `cart` table and adding one is out of scope, the cart is an
in-memory Python dict in `cart.py`: `{customer_id: {product_id: quantity}}`. It lives
in process memory, resets on server restart, and is not safe across multiple worker
processes — acceptable for a single `--reload` dev process on a learning project.
`POST /cart/add` mutates it; `GET /cart` renders it by joining against `products` for
name/price/stock; `POST /cart/checkout` consumes it and clears the customer's entry
on success.

## Customer switching

No auth. `base.html` renders a `<select>` of `customer_id, full_name` from
`customers`, submitted as a query param (`?customer_id=`) or hidden form field on
every page/action that needs it. No cookies, no sessions.

## Order placement transaction (`POST /cart/checkout`)

Reuses the 2PL pattern from `concurrency_demo.py`'s `buy_with_lock`:

1. Open a transaction (`autocommit = False`).
2. For each `(product_id, qty)` in the customer's cart, sorted by `product_id`
   (fixed lock order avoids cross-checkout deadlocks), run
   `SELECT stock, price FROM products WHERE product_id = %s FOR UPDATE`.
3. If any requested `qty` exceeds the locked `stock`, `ROLLBACK` and re-render the
   cart with an error message — no partial writes.
4. `INSERT INTO orders (customer_id, shipping_city, ...) RETURNING order_id`.
5. `INSERT INTO order_items (order_id, product_id, quantity, unit_price)` per line,
   using the price read in step 2 (price-at-purchase-time, matching the schema's
   existing intent).
6. `UPDATE orders SET total_amount = %s WHERE order_id = %s` with the summed total.
7. `INSERT INTO payments (order_id, payment_method, amount, payment_status)` —
   method comes from a simple `<select>` on the checkout form, status hardcoded to
   `SUCCESS` (no real payment gateway).
8. `UPDATE products SET stock = stock - %s WHERE product_id = %s` per line.
9. `COMMIT`; clear the in-memory cart entry for that customer; redirect to the new
   order's detail view.

Any exception at any step triggers `ROLLBACK` and an error is shown to the user;
no order/order_items/payment rows are left behind on failure.

## Pages / routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Catalog: all products, optional `?category=` filter, shows stock |
| GET | `/products/{product_id}` | Product detail + "add to cart" form |
| POST | `/cart/add` | Add `{product_id, qty}` to the current customer's cart |
| GET | `/cart` | Review cart lines, totals, checkout form (payment method) |
| POST | `/cart/checkout` | Runs the transaction above |
| GET | `/orders?customer_id=` | List orders for a customer: status, total, date |
| GET | `/support?customer_id=` | List tickets for a customer + submission form |
| POST | `/support/new` | Insert a `support_tickets` row |
| GET | `/admin` | Read-only tables: customers, products, orders, payments |

## Error handling

- Checkout: insufficient stock → rollback + inline error, no exception surfaced raw.
- Empty cart checkout → rejected before opening a transaction.
- Unknown `product_id` / `customer_id` in a URL → 404 via FastAPI's `HTTPException`.
- No input validation framework — FastAPI's basic form/query typing is sufficient
  given there's no auth boundary to defend.

## Testing

Manual verification: start `uvicorn main:app --reload`, walk through catalog →
product detail → add to cart → checkout → orders → support ticket → admin, using the
seeded data from `seed.py`. Confirm a checkout that exceeds stock is rejected and
leaves no partial rows (`SELECT` counts on `orders`/`order_items`/`payments` before
and after). No automated test suite requested.

## Out of scope

- Authentication/authorization
- Schema changes of any kind
- ORM / query builder
- Persistent (DB- or cookie-backed) cart
- Payment gateway integration
- Order status transitions (admin editing orders/payments) — admin is read-only per
  the request
