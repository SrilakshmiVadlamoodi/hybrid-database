from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from db import get_cursor
from routes.common import get_all_customers, parse_customer_id
from templates import templates

router = APIRouter()


@router.get("/orders", response_class=HTMLResponse)
def list_orders(request: Request, customer_id: str | None = None):
    customer_id = parse_customer_id(customer_id)
    with get_cursor() as (conn, cur):
        orders = []
        if customer_id is not None:
            cur.execute(
                "SELECT order_id, order_date, status, total_amount, shipping_city "
                "FROM orders WHERE customer_id = %s ORDER BY order_date DESC",
                (customer_id,),
            )
            orders = cur.fetchall()
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        request,
        "orders.html",
        {"orders": orders, "customers": customers, "customer_id": customer_id},
    )
