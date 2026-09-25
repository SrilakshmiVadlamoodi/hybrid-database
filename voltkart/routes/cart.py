from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import cart as cart_store
from db import get_cursor
from routes.common import get_all_customers, parse_customer_id
from templates import templates

router = APIRouter()


@router.post("/cart/add")
def add_to_cart(customer_id: int = Form(...), product_id: int = Form(...), qty: int = Form(...)):
    if qty < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")
    cart_store.add_to_cart(customer_id, product_id, qty)
    return RedirectResponse(url=f"/cart?customer_id={customer_id}", status_code=303)


@router.post("/cart/clear")
def clear_cart(customer_id: int = Form(...)):
    cart_store.clear_cart(customer_id)
    return RedirectResponse(url=f"/cart?customer_id={customer_id}", status_code=303)


@router.get("/cart", response_class=HTMLResponse)
def view_cart(request: Request, customer_id: str | None = None, error: str | None = None):
    customer_id = parse_customer_id(customer_id)
    lines = []
    total = 0
    with get_cursor() as (conn, cur):
        if customer_id is not None:
            cart = cart_store.get_cart(customer_id)
            for product_id, qty in cart.items():
                cur.execute(
                    "SELECT product_id, product_name, price, stock FROM products WHERE product_id = %s",
                    (product_id,),
                )
                product = cur.fetchone()
                if not product:
                    lines.append(
                        {
                            "product_id": product_id,
                            "product_name": f"Product {product_id} (no longer available)",
                            "price": 0,
                            "qty": qty,
                            "line_total": 0,
                        }
                    )
                    continue
                line_total = float(product["price"]) * qty
                total += line_total
                lines.append({**product, "qty": qty, "line_total": line_total})
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        request,
        "cart.html",
        {
            "lines": lines,
            "total": total,
            "customers": customers,
            "customer_id": customer_id,
            "error": error,
        },
    )


@router.post("/cart/checkout")
def checkout(customer_id: int = Form(...), shipping_city: str = Form(...), payment_method: str = Form(...)):
    cart = cart_store.take_cart(customer_id)
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
            cart_store.restore_cart(customer_id, cart)
            error_msg = str(exc).replace(" ", "+")
            return RedirectResponse(
                url=f"/cart?customer_id={customer_id}&error={error_msg}",
                status_code=303,
            )

    return RedirectResponse(url=f"/orders?customer_id={customer_id}", status_code=303)
