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
