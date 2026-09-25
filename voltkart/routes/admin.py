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
        request,
        "admin.html",
        {
            "customers_table": customers_table,
            "products": products,
            "orders": orders,
            "payments": payments,
            "customers": customers,
            "customer_id": None,
        },
    )
