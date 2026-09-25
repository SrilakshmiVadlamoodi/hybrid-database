# VoltKart Web Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal FastAPI + Jinja2 web frontend inside `voltkart/` that lets a user browse products, manage an in-memory cart, place orders through the existing 2PL stock-locking transaction, view orders, submit/view support tickets, and browse a read-only admin panel.

**Architecture:** A FastAPI app (`main.py`) mounts one `APIRouter` per feature area (`routes/catalog.py`, `routes/cart.py`, `routes/orders.py`, `routes/support.py`, `routes/admin.py`). All DB access goes through a shared `psycopg2` connection pool (`db.py`) using raw parameterized SQL — no ORM. The cart is a process-local in-memory dict (`cart.py`), since the schema has no cart table and none may be added. Server-rendered Jinja2 templates (`templates/`) share a `base.html` with a customer-switcher dropdown.

**Tech Stack:** FastAPI, Jinja2 (via `fastapi.templating.Jinja2Templates`), `psycopg2` (raw SQL), `python-dotenv`, `uvicorn`.

**Spec:** `docs/superpowers/specs/2026-09-25-voltkart-web-frontend-design.md`

## Global Constraints

- Raw SQL only — no ORM, no query builder.
- Reuse `schema.sql` exactly as-is — no migrations, no new tables/columns.
- No authentication — customer identity comes from a `customer_id` query param / hidden form field, driven by a dropdown populated from `customers`.
- Cart state is an in-memory `dict` in `cart.py` (`{customer_id: {product_id: qty}}`) — not persisted to any database, resets on restart.
- Checkout must reuse the 2PL pattern from `voltkart/concurrency_demo.py`'s `buy_with_lock`: `SELECT ... FOR UPDATE` on every product row involved, acquired in ascending `product_id` order, before any writes.
- Credentials come from `voltkart/.env` via `python-dotenv`, same env var names already used by `concurrency_demo.py` / `seed.py` (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`).
- Entry point: `uvicorn main:app --reload`, run from inside `voltkart/`, port 8000 (uvicorn's default).
- All new files live inside `voltkart/`.
- Per the spec's Testing section, no automated test suite is requested — each task is verified manually (curl / browser / `psql`) instead of with `pytest`. Steps below substitute "write the file" + "manually verify" for the usual "write failing test" + "implement" cycle.

## Review Focus

- Checkout requesting more units than are currently in stock must be rejected with no partial `orders`/`order_items`/`payments`/`products.stock` writes (Task 4).
- Checkout submitted with an empty cart must be rejected before any transaction is opened (Task 4).
- `GET /products/{product_id}` for a nonexistent `product_id` must return a 404, not an unhandled exception (Task 3).
- A cart line whose `product_id` no longer exists in `products` by checkout time must abort the transaction cleanly rather than crash (Task 4).
- Checkout locks rows in ascending `product_id` order specifically so two overlapping multi-item checkouts can't deadlock each other (Task 4 — verified by code inspection, since simulating true concurrency is out of scope without an automated test harness).

---

## Task 1: Dependencies, DB pool, cart store, and app scaffolding

**Files:**
- Modify: `voltkart/requirements.txt`
- Create: `voltkart/db.py`
- Create: `voltkart/cart.py`
- Create: `voltkart/templates.py`
- Create: `voltkart/static/style.css`
- Create: `voltkart/routes/__init__.py`
- Create: `voltkart/routes/common.py`
- Create: `voltkart/main.py`

**Interfaces:**
- Produces: `db.get_cursor(autocommit=True)` — context manager yielding `(conn, cur)` where `cur` is a `psycopg2.extras.RealDictCursor`.
- Produces: `cart.get_cart(customer_id: int) -> dict[int, int]`, `cart.add_to_cart(customer_id: int, product_id: int, qty: int) -> None`, `cart.clear_cart(customer_id: int) -> None`.
- Produces: `templates.templates` — a `Jinja2Templates` instance pointed at `voltkart/templates/`.
- Produces: `routes.common.get_all_customers(cur) -> list[dict]`.
- Produces: `main.app` — the FastAPI instance, with `/static` mounted. No routers included yet (added in later tasks).

- [ ] **Step 1: Update `requirements.txt`**

```
psycopg2-binary>=2.9.10
pymongo>=4.8.0
faker>=26.0.0
python-dotenv>=1.0.1
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
jinja2>=3.1.4
python-multipart>=0.0.9
```

- [ ] **Step 2: Create `db.py`**

```python
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from psycopg2 import pool

load_dotenv()

_pool = pool.SimpleConnectionPool(
    1,
    10,
    host=os.getenv("PGHOST", "localhost"),
    port=os.getenv("PGPORT", "5432"),
    user=os.getenv("PGUSER", "postgres"),
    password=os.getenv("PGPASSWORD", ""),
    dbname=os.getenv("PGDATABASE", "voltkart"),
)


@contextmanager
def get_conn(autocommit=True):
    conn = _pool.getconn()
    conn.autocommit = autocommit
    try:
        yield conn
    finally:
        conn.autocommit = True
        _pool.putconn(conn)


@contextmanager
def get_cursor(autocommit=True):
    with get_conn(autocommit=autocommit) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield conn, cur
```

- [ ] **Step 3: Create `cart.py`**

```python
_carts: dict[int, dict[int, int]] = {}


def get_cart(customer_id: int) -> dict[int, int]:
    return _carts.setdefault(customer_id, {})


def add_to_cart(customer_id: int, product_id: int, qty: int) -> None:
    cart = get_cart(customer_id)
    cart[product_id] = cart.get(product_id, 0) + qty


def clear_cart(customer_id: int) -> None:
    _carts.pop(customer_id, None)
```

- [ ] **Step 4: Create `templates.py`**

```python
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
```

- [ ] **Step 5: Create `static/style.css`**

```css
body {
  font-family: system-ui, sans-serif;
  margin: 0;
  padding: 0 1.5rem 2rem;
  color: #1a1a1a;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
  border-bottom: 1px solid #ddd;
  margin-bottom: 1.5rem;
}

nav a {
  margin-right: 1rem;
  text-decoration: none;
  color: #0b5fff;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
}

th, td {
  text-align: left;
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid #eee;
}

.error {
  color: #b00020;
  font-weight: bold;
}

form label {
  margin-right: 0.4rem;
}

form {
  margin: 0.75rem 0;
}
```

- [ ] **Step 6: Create `routes/__init__.py`** (empty)

```python
```

- [ ] **Step 7: Create `routes/common.py`**

```python
def get_all_customers(cur):
    cur.execute("SELECT customer_id, full_name FROM customers ORDER BY full_name")
    return cur.fetchall()
```

- [ ] **Step 8: Create `main.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")
```

- [ ] **Step 9: Install dependencies and verify the app boots**

Run (from `voltkart/`):
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
In another terminal:
```bash
curl -I http://127.0.0.1:8000/static/style.css
```
Expected: `HTTP/1.1 200 OK` with `content-type: text/css`.

- [ ] **Step 10: Verify the DB pool and cart store work**

Run (from `voltkart/`, server can stay up):
```bash
python -c "from db import get_cursor; \
c = get_cursor(); \
conn, cur = c.__enter__(); \
cur.execute('SELECT COUNT(*) AS n FROM customers'); \
print(cur.fetchone()); \
c.__exit__(None, None, None)"
python -c "import cart; cart.add_to_cart(1, 5, 2); print(cart.get_cart(1)); cart.clear_cart(1); print(cart.get_cart(1))"
```
Expected: first command prints `{'n': 60}` (or however many customers `seed.py` created); second prints `{5: 2}` then `{}`.

- [ ] **Step 11: Commit**

```bash
git add voltkart/requirements.txt voltkart/db.py voltkart/cart.py voltkart/templates.py voltkart/static/style.css voltkart/routes/__init__.py voltkart/routes/common.py voltkart/main.py
git commit -m "Add FastAPI scaffolding, DB pool, and in-memory cart store"
```

---

## Task 2: Catalog routes (home + product detail) and base template

**Files:**
- Create: `voltkart/templates/base.html`
- Create: `voltkart/templates/catalog.html`
- Create: `voltkart/templates/product_detail.html`
- Create: `voltkart/routes/catalog.py`
- Modify: `voltkart/main.py`

**Interfaces:**
- Consumes: `db.get_cursor`, `routes.common.get_all_customers` (Task 1).
- Produces: `routes.catalog.router` — a FastAPI `APIRouter` with `GET /` and `GET /products/{product_id}`, included into `main.app` in this task.
- Produces template context variables every later template can rely on being passed by its route: `customers`, `customer_id`.

- [ ] **Step 1: Create `templates/base.html`**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>VoltKart</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <nav>
      <a href="/?customer_id={{ customer_id or '' }}">Catalog</a>
      <a href="/cart?customer_id={{ customer_id or '' }}">Cart</a>
      <a href="/orders?customer_id={{ customer_id or '' }}">Orders</a>
      <a href="/support?customer_id={{ customer_id or '' }}">Support</a>
      <a href="/admin">Admin</a>
    </nav>
    <form method="get" action="{{ request.url.path }}" class="customer-switcher">
      <label for="customer_id">Customer:</label>
      <select name="customer_id" id="customer_id" onchange="this.form.submit()">
        <option value="">-- select --</option>
        {% for c in customers %}
        <option value="{{ c.customer_id }}" {% if customer_id == c.customer_id %}selected{% endif %}>{{ c.full_name }}</option>
        {% endfor %}
      </select>
    </form>
  </header>
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Create `templates/catalog.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Products</h1>
<form method="get" action="/">
  <input type="hidden" name="customer_id" value="{{ customer_id or '' }}">
  <label for="category">Category:</label>
  <select name="category" id="category" onchange="this.form.submit()">
    <option value="">All</option>
    {% for cat in categories %}
    <option value="{{ cat }}" {% if selected_category == cat %}selected{% endif %}>{{ cat }}</option>
    {% endfor %}
  </select>
</form>
<table>
  <tr><th>Name</th><th>Category</th><th>Brand</th><th>Price</th><th>Stock</th><th></th></tr>
  {% for p in products %}
  <tr>
    <td>{{ p.product_name }}</td>
    <td>{{ p.category }}</td>
    <td>{{ p.brand }}</td>
    <td>₹{{ p.price }}</td>
    <td>{{ p.stock }}</td>
    <td><a href="/products/{{ p.product_id }}?customer_id={{ customer_id or '' }}">View</a></td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 3: Create `templates/product_detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ product.product_name }}</h1>
<p>Category: {{ product.category }} | Brand: {{ product.brand }}</p>
<p>Price: ₹{{ product.price }}</p>
<p>Stock: {{ product.stock }}</p>
<p>Warranty: {{ product.warranty_months }} months</p>

{% if customer_id %}
<form method="post" action="/cart/add">
  <input type="hidden" name="customer_id" value="{{ customer_id }}">
  <input type="hidden" name="product_id" value="{{ product.product_id }}">
  <label for="qty">Quantity:</label>
  <input type="number" name="qty" id="qty" value="1" min="1" max="{{ product.stock }}">
  <button type="submit" {% if product.stock == 0 %}disabled{% endif %}>Add to cart</button>
</form>
{% else %}
<p>Select a customer above to add this product to a cart.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Create `routes/catalog.py`**

```python
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from db import get_cursor
from routes.common import get_all_customers
from templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, category: str | None = None, customer_id: int | None = None):
    with get_cursor() as (conn, cur):
        if category:
            cur.execute(
                "SELECT product_id, product_name, category, brand, price, stock "
                "FROM products WHERE category = %s ORDER BY product_name",
                (category,),
            )
        else:
            cur.execute(
                "SELECT product_id, product_name, category, brand, price, stock "
                "FROM products ORDER BY product_name"
            )
        products = cur.fetchall()
        cur.execute("SELECT DISTINCT category FROM products ORDER BY category")
        categories = [row["category"] for row in cur.fetchall()]
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        "catalog.html",
        {
            "request": request,
            "products": products,
            "categories": categories,
            "selected_category": category,
            "customers": customers,
            "customer_id": customer_id,
        },
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, customer_id: int | None = None):
    with get_cursor() as (conn, cur):
        cur.execute(
            "SELECT product_id, product_name, category, brand, price, stock, warranty_months "
            "FROM products WHERE product_id = %s",
            (product_id,),
        )
        product = cur.fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        "product_detail.html",
        {"request": request, "product": product, "customers": customers, "customer_id": customer_id},
    )
```

- [ ] **Step 5: Wire the router into `main.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import catalog

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(catalog.router)
```

- [ ] **Step 6: Manually verify**

With `uvicorn main:app --reload` running from `voltkart/`:
```bash
curl -s http://127.0.0.1:8000/ | grep -o "<h1>Products</h1>"
curl -s "http://127.0.0.1:8000/?category=Laptop" | grep -c "<tr>"
curl -s http://127.0.0.1:8000/products/1 | grep -o "<h1>.*</h1>"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/products/999999
```
Expected: first prints the `<h1>` match; second prints a row count > 1 (header row + at least one laptop, assuming seeded data includes laptops); third prints the product's name in an `<h1>`; fourth prints `404`.

- [ ] **Step 7: Commit**

```bash
git add voltkart/templates/base.html voltkart/templates/catalog.html voltkart/templates/product_detail.html voltkart/routes/catalog.py voltkart/main.py
git commit -m "Add catalog and product detail pages"
```

---

## Task 3: Cart view and add-to-cart route (no checkout yet)

**Files:**
- Create: `voltkart/templates/cart.html`
- Create: `voltkart/routes/cart.py`
- Modify: `voltkart/main.py`

**Interfaces:**
- Consumes: `cart.get_cart`, `cart.add_to_cart` (Task 1); `db.get_cursor`, `routes.common.get_all_customers` (Task 1).
- Produces: `routes.cart.router` with `POST /cart/add` and `GET /cart` (checkout endpoint `POST /cart/checkout` added in Task 4 in the same file).

- [ ] **Step 1: Create `templates/cart.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Cart</h1>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if not customer_id %}
<p>Select a customer above to view a cart.</p>
{% elif not lines %}
<p>Cart is empty.</p>
{% else %}
<table>
  <tr><th>Product</th><th>Price</th><th>Qty</th><th>Line total</th></tr>
  {% for line in lines %}
  <tr>
    <td>{{ line.product_name }}</td>
    <td>₹{{ line.price }}</td>
    <td>{{ line.qty }}</td>
    <td>₹{{ "%.2f"|format(line.line_total) }}</td>
  </tr>
  {% endfor %}
</table>
<p>Total: ₹{{ "%.2f"|format(total) }}</p>

<form method="post" action="/cart/checkout">
  <input type="hidden" name="customer_id" value="{{ customer_id }}">
  <label for="shipping_city">Shipping city:</label>
  <input type="text" name="shipping_city" id="shipping_city" required>
  <label for="payment_method">Payment method:</label>
  <select name="payment_method" id="payment_method">
    <option value="CARD">Card</option>
    <option value="UPI">UPI</option>
    <option value="NETBANKING">Net banking</option>
    <option value="COD">Cash on delivery</option>
    <option value="WALLET">Wallet</option>
  </select>
  <button type="submit">Place order</button>
</form>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Create `routes/cart.py`** (add + view only; checkout added in Task 4)

```python
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import cart as cart_store
from db import get_cursor
from routes.common import get_all_customers
from templates import templates

router = APIRouter()


@router.post("/cart/add")
def add_to_cart(customer_id: int = Form(...), product_id: int = Form(...), qty: int = Form(...)):
    if qty < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")
    cart_store.add_to_cart(customer_id, product_id, qty)
    return RedirectResponse(url=f"/cart?customer_id={customer_id}", status_code=303)


@router.get("/cart", response_class=HTMLResponse)
def view_cart(request: Request, customer_id: int, error: str | None = None):
    cart = cart_store.get_cart(customer_id)
    lines = []
    total = 0
    with get_cursor() as (conn, cur):
        for product_id, qty in cart.items():
            cur.execute(
                "SELECT product_id, product_name, price, stock FROM products WHERE product_id = %s",
                (product_id,),
            )
            product = cur.fetchone()
            if not product:
                continue
            line_total = float(product["price"]) * qty
            total += line_total
            lines.append({**product, "qty": qty, "line_total": line_total})
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "lines": lines,
            "total": total,
            "customers": customers,
            "customer_id": customer_id,
            "error": error,
        },
    )
```

- [ ] **Step 3: Wire the router into `main.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import cart, catalog

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(catalog.router)
app.include_router(cart.router)
```

- [ ] **Step 4: Manually verify**

```bash
curl -s -X POST http://127.0.0.1:8000/cart/add -d "customer_id=1&product_id=1&qty=2" -o /dev/null -w "%{http_code}\n"
curl -s "http://127.0.0.1:8000/cart?customer_id=1" | grep -o "Total: ₹[0-9.]*"
```
Expected: first prints `303`; second prints a `Total: ₹...` line reflecting `2 × products.price` for `product_id=1`.

- [ ] **Step 5: Commit**

```bash
git add voltkart/templates/cart.html voltkart/routes/cart.py voltkart/main.py
git commit -m "Add cart view and add-to-cart route"
```

---

## Task 4: Checkout transaction (2PL order placement)

**Files:**
- Modify: `voltkart/routes/cart.py`

**Interfaces:**
- Consumes: `cart.get_cart`, `cart.clear_cart`; `db.get_cursor(autocommit=False)`.
- Produces: `POST /cart/checkout`, redirecting to `/orders?customer_id=` on success or back to `/cart?customer_id=&error=` on failure.

- [ ] **Step 1: Append the checkout route to `routes/cart.py`**

```python
@router.post("/cart/checkout")
def checkout(customer_id: int = Form(...), shipping_city: str = Form(...), payment_method: str = Form(...)):
    cart = cart_store.get_cart(customer_id)
    if not cart:
        return RedirectResponse(url=f"/cart?customer_id={customer_id}&error=Cart+is+empty", status_code=303)

    with get_cursor(autocommit=False) as (conn, cur):
        try:
            total = 0
            locked_lines = []
            for product_id in sorted(cart.keys()):
                qty = cart[product_id]
                cur.execute(
                    "SELECT price, stock FROM products WHERE product_id = %s FOR UPDATE",
                    (product_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Product {product_id} no longer exists")
                if row["stock"] < qty:
                    raise ValueError(
                        f"Only {row['stock']} left in stock for product {product_id}, requested {qty}"
                    )
                locked_lines.append((product_id, qty, row["price"]))
                total += float(row["price"]) * qty

            cur.execute(
                "INSERT INTO orders (customer_id, status, total_amount, shipping_city) "
                "VALUES (%s, 'PLACED', %s, %s) RETURNING order_id",
                (customer_id, total, shipping_city),
            )
            order_id = cur.fetchone()["order_id"]

            for product_id, qty, unit_price in locked_lines:
                cur.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                    "VALUES (%s, %s, %s, %s)",
                    (order_id, product_id, qty, unit_price),
                )
                cur.execute(
                    "UPDATE products SET stock = stock - %s WHERE product_id = %s",
                    (qty, product_id),
                )

            cur.execute(
                "INSERT INTO payments (order_id, payment_method, amount, payment_status) "
                "VALUES (%s, %s, %s, 'SUCCESS')",
                (order_id, payment_method, total),
            )

            conn.commit()
        except Exception as exc:
            conn.rollback()
            error_msg = str(exc).replace(" ", "+")
            return RedirectResponse(
                url=f"/cart?customer_id={customer_id}&error={error_msg}",
                status_code=303,
            )

    cart_store.clear_cart(customer_id)
    return RedirectResponse(url=f"/orders?customer_id={customer_id}", status_code=303)
```

- [ ] **Step 2: Manually verify the happy path**

```bash
psql -U postgres -d voltkart -c "SELECT COUNT(*) FROM orders;"
curl -s -X POST http://127.0.0.1:8000/cart/add -d "customer_id=2&product_id=3&qty=1" -o /dev/null
curl -s -i -X POST http://127.0.0.1:8000/cart/checkout \
  -d "customer_id=2&shipping_city=Pune&payment_method=UPI" | head -1
psql -U postgres -d voltkart -c "SELECT COUNT(*) FROM orders;"
psql -U postgres -d voltkart -c "SELECT o.order_id, oi.product_id, oi.quantity, p.payment_status FROM orders o JOIN order_items oi USING(order_id) JOIN payments p USING(order_id) WHERE o.customer_id = 2 ORDER BY o.order_id DESC LIMIT 1;"
```
Expected: order count increases by 1; the redirect response line shows `303`; the last query shows the new order with a matching `order_items` row and `payment_status = SUCCESS`.

- [ ] **Step 3: Manually verify the insufficient-stock path rolls back cleanly**

```bash
psql -U postgres -d voltkart -c "SELECT product_id, stock FROM products WHERE product_id = 3;"
# Note the stock value, call it N
curl -s -X POST http://127.0.0.1:8000/cart/add -d "customer_id=2&product_id=3&qty=999999" -o /dev/null
psql -U postgres -d voltkart -c "SELECT COUNT(*) FROM orders;"
curl -s -i -X POST http://127.0.0.1:8000/cart/checkout \
  -d "customer_id=2&shipping_city=Pune&payment_method=UPI" | grep -i location
psql -U postgres -d voltkart -c "SELECT COUNT(*) FROM orders;"
psql -U postgres -d voltkart -c "SELECT product_id, stock FROM products WHERE product_id = 3;"
```
Expected: order count is unchanged before and after; the `Location` header points back to `/cart?...&error=...`; `products.stock` for `product_id = 3` is unchanged from `N`.

- [ ] **Step 4: Commit**

```bash
git add voltkart/routes/cart.py
git commit -m "Add checkout transaction with row-locked stock decrement"
```

---

## Task 5: Orders and support routes

**Files:**
- Create: `voltkart/templates/orders.html`
- Create: `voltkart/templates/support.html`
- Create: `voltkart/routes/orders.py`
- Create: `voltkart/routes/support.py`
- Modify: `voltkart/main.py`

**Interfaces:**
- Consumes: `db.get_cursor`, `routes.common.get_all_customers` (Task 1).
- Produces: `routes.orders.router` (`GET /orders`), `routes.support.router` (`GET /support`, `POST /support/new`), both included into `main.app`.

- [ ] **Step 1: Create `templates/orders.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Orders</h1>
{% if not customer_id %}
<p>Select a customer above to view orders.</p>
{% elif not orders %}
<p>No orders yet.</p>
{% else %}
<table>
  <tr><th>Order ID</th><th>Date</th><th>Status</th><th>Total</th><th>Shipping city</th></tr>
  {% for o in orders %}
  <tr>
    <td>{{ o.order_id }}</td>
    <td>{{ o.order_date }}</td>
    <td>{{ o.status }}</td>
    <td>₹{{ o.total_amount }}</td>
    <td>{{ o.shipping_city }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Create `templates/support.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Support tickets</h1>
{% if not customer_id %}
<p>Select a customer above to view or submit tickets.</p>
{% else %}
<h2>Submit a ticket</h2>
<form method="post" action="/support/new">
  <input type="hidden" name="customer_id" value="{{ customer_id }}">
  <label for="subject">Subject:</label>
  <input type="text" name="subject" id="subject" required>
  <label for="category">Category:</label>
  <select name="category" id="category">
    {% for cat in categories %}
    <option value="{{ cat }}">{{ cat }}</option>
    {% endfor %}
  </select>
  <label for="order_id">Order ID (optional):</label>
  <input type="number" name="order_id" id="order_id">
  <button type="submit">Submit</button>
</form>

<h2>Your tickets</h2>
{% if not tickets %}
<p>No tickets yet.</p>
{% else %}
<table>
  <tr><th>ID</th><th>Subject</th><th>Category</th><th>Status</th><th>Created</th></tr>
  {% for t in tickets %}
  <tr>
    <td>{{ t.ticket_id }}</td>
    <td>{{ t.subject }}</td>
    <td>{{ t.category }}</td>
    <td>{{ t.status }}</td>
    <td>{{ t.created_at }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Create `routes/orders.py`**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from db import get_cursor
from routes.common import get_all_customers
from templates import templates

router = APIRouter()


@router.get("/orders", response_class=HTMLResponse)
def list_orders(request: Request, customer_id: int):
    with get_cursor() as (conn, cur):
        cur.execute(
            "SELECT order_id, order_date, status, total_amount, shipping_city "
            "FROM orders WHERE customer_id = %s ORDER BY order_date DESC",
            (customer_id,),
        )
        orders = cur.fetchall()
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        "orders.html",
        {"request": request, "orders": orders, "customers": customers, "customer_id": customer_id},
    )
```

- [ ] **Step 4: Create `routes/support.py`**

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from db import get_cursor
from routes.common import get_all_customers
from templates import templates

router = APIRouter()

CATEGORIES = ["DELIVERY", "PRODUCT_DEFECT", "PAYMENT", "RETURN", "GENERAL"]


@router.get("/support", response_class=HTMLResponse)
def list_tickets(request: Request, customer_id: int):
    with get_cursor() as (conn, cur):
        cur.execute(
            "SELECT ticket_id, order_id, subject, category, status, created_at "
            "FROM support_tickets WHERE customer_id = %s ORDER BY created_at DESC",
            (customer_id,),
        )
        tickets = cur.fetchall()
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        "support.html",
        {
            "request": request,
            "tickets": tickets,
            "customers": customers,
            "customer_id": customer_id,
            "categories": CATEGORIES,
        },
    )


@router.post("/support/new")
def create_ticket(
    customer_id: int = Form(...),
    subject: str = Form(...),
    category: str = Form(...),
    order_id: str = Form(""),
):
    with get_cursor() as (conn, cur):
        cur.execute(
            "INSERT INTO support_tickets (customer_id, order_id, subject, category) "
            "VALUES (%s, %s, %s, %s)",
            (customer_id, int(order_id) if order_id else None, subject, category),
        )
    return RedirectResponse(url=f"/support?customer_id={customer_id}", status_code=303)
```

- [ ] **Step 5: Wire both routers into `main.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import cart, catalog, orders, support

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(catalog.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(support.router)
```

- [ ] **Step 6: Manually verify**

```bash
curl -s "http://127.0.0.1:8000/orders?customer_id=2" | grep -c "<tr>"
curl -s -X POST http://127.0.0.1:8000/support/new \
  -d "customer_id=2&subject=Test+ticket&category=GENERAL&order_id=" \
  -o /dev/null -w "%{http_code}\n"
curl -s "http://127.0.0.1:8000/support?customer_id=2" | grep -o "Test ticket"
```
Expected: first shows at least 2 rows (header + the order from Task 4); second prints `303`; third prints `Test ticket`.

- [ ] **Step 7: Commit**

```bash
git add voltkart/templates/orders.html voltkart/templates/support.html voltkart/routes/orders.py voltkart/routes/support.py voltkart/main.py
git commit -m "Add orders list and support ticket pages"
```

---

## Task 6: Admin panel (read-only)

**Files:**
- Create: `voltkart/templates/admin.html`
- Create: `voltkart/routes/admin.py`
- Modify: `voltkart/main.py`

**Interfaces:**
- Consumes: `db.get_cursor`, `routes.common.get_all_customers` (Task 1).
- Produces: `routes.admin.router` (`GET /admin`), included into `main.app`.

- [ ] **Step 1: Create `templates/admin.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Admin</h1>

<h2>Customers</h2>
<table>
  <tr><th>ID</th><th>Name</th><th>Email</th><th>City</th><th>State</th><th>Signup date</th></tr>
  {% for c in customers_table %}
  <tr><td>{{ c.customer_id }}</td><td>{{ c.full_name }}</td><td>{{ c.email }}</td><td>{{ c.city }}</td><td>{{ c.state }}</td><td>{{ c.signup_date }}</td></tr>
  {% endfor %}
</table>

<h2>Products</h2>
<table>
  <tr><th>ID</th><th>Name</th><th>Category</th><th>Brand</th><th>Price</th><th>Stock</th></tr>
  {% for p in products %}
  <tr><td>{{ p.product_id }}</td><td>{{ p.product_name }}</td><td>{{ p.category }}</td><td>{{ p.brand }}</td><td>₹{{ p.price }}</td><td>{{ p.stock }}</td></tr>
  {% endfor %}
</table>

<h2>Orders</h2>
<table>
  <tr><th>ID</th><th>Customer ID</th><th>Date</th><th>Status</th><th>Total</th></tr>
  {% for o in orders %}
  <tr><td>{{ o.order_id }}</td><td>{{ o.customer_id }}</td><td>{{ o.order_date }}</td><td>{{ o.status }}</td><td>₹{{ o.total_amount }}</td></tr>
  {% endfor %}
</table>

<h2>Payments</h2>
<table>
  <tr><th>ID</th><th>Order ID</th><th>Method</th><th>Amount</th><th>Status</th><th>Paid at</th></tr>
  {% for pay in payments %}
  <tr><td>{{ pay.payment_id }}</td><td>{{ pay.order_id }}</td><td>{{ pay.payment_method }}</td><td>₹{{ pay.amount }}</td><td>{{ pay.payment_status }}</td><td>{{ pay.paid_at }}</td></tr>
  {% endfor %}
</table>
{% endblock %}
```

Note: the nav's customer dropdown uses the `customers` context variable (Task 2's `base.html`), so this route passes the full customer list as both `customers` (for the nav) and `customers_table` (for the admin table) to avoid a name collision.

- [ ] **Step 2: Create `routes/admin.py`**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from db import get_cursor
from routes.common import get_all_customers
from templates import templates

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    with get_cursor() as (conn, cur):
        cur.execute(
            "SELECT customer_id, full_name, email, city, state, signup_date "
            "FROM customers ORDER BY customer_id"
        )
        customers_table = cur.fetchall()
        cur.execute(
            "SELECT product_id, product_name, category, brand, price, stock "
            "FROM products ORDER BY product_id"
        )
        products = cur.fetchall()
        cur.execute(
            "SELECT order_id, customer_id, order_date, status, total_amount "
            "FROM orders ORDER BY order_id DESC"
        )
        orders = cur.fetchall()
        cur.execute(
            "SELECT payment_id, order_id, payment_method, amount, payment_status, paid_at "
            "FROM payments ORDER BY payment_id DESC"
        )
        payments = cur.fetchall()
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "customers_table": customers_table,
            "products": products,
            "orders": orders,
            "payments": payments,
            "customers": customers,
            "customer_id": None,
        },
    )
```

- [ ] **Step 3: Wire the router into `main.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import admin, cart, catalog, orders, support

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(catalog.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(support.router)
app.include_router(admin.router)
```

- [ ] **Step 4: Manually verify**

```bash
curl -s http://127.0.0.1:8000/admin | grep -o "<h2>Payments</h2>"
curl -s http://127.0.0.1:8000/admin | grep -c "<tr>"
```
Expected: first prints the match; second prints a row count consistent with `customers + products + orders + payments` counts plus 4 header rows.

- [ ] **Step 5: Commit**

```bash
git add voltkart/templates/admin.html voltkart/routes/admin.py voltkart/main.py
git commit -m "Add read-only admin panel"
```

---

## Task 7: End-to-end walkthrough

**Files:** none (verification only).

- [ ] **Step 1: Full manual walkthrough**

With `uvicorn main:app --reload` running from `voltkart/`, in a browser:
1. Open `http://127.0.0.1:8000/`, pick a customer from the dropdown, filter by category.
2. Click into a product, add 1 unit to cart.
3. Go to Cart, fill in shipping city and payment method, place the order.
4. Confirm redirect to Orders shows the new order with correct total.
5. Go to Support, submit a ticket referencing the new order, confirm it appears in "Your tickets".
6. Go to Admin, confirm the new customer's order, its order line, and its payment all appear in the respective tables, and the product's stock decreased by 1 versus its value before step 2.

- [ ] **Step 2: Confirm the app matches the spec's stated entry point**

```bash
# from voltkart/
uvicorn main:app --reload
```
Expected: server starts on `http://127.0.0.1:8000` with no import errors.

No commit for this task (verification only).
