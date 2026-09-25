from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from db import get_cursor
from routes.common import get_all_customers, parse_customer_id
from templates import templates

router = APIRouter()

CATEGORIES = ["DELIVERY", "PRODUCT_DEFECT", "PAYMENT", "RETURN", "GENERAL"]


@router.get("/support", response_class=HTMLResponse)
def list_tickets(request: Request, customer_id: str | None = None, error: str | None = None):
    customer_id = parse_customer_id(customer_id)
    with get_cursor() as (conn, cur):
        tickets = []
        if customer_id is not None:
            cur.execute(
                "SELECT ticket_id, order_id, subject, category, status, created_at "
                "FROM support_tickets WHERE customer_id = %s ORDER BY created_at DESC",
                (customer_id,),
            )
            tickets = cur.fetchall()
        customers = get_all_customers(cur)
    return templates.TemplateResponse(
        request,
        "support.html",
        {
            "tickets": tickets,
            "customers": customers,
            "customer_id": customer_id,
            "categories": CATEGORIES,
            "error": error,
        },
    )


@router.post("/support/new")
def create_ticket(
    customer_id: int = Form(...),
    subject: str = Form(...),
    category: str = Form(...),
    order_id: str = Form(""),
):
    try:
        order_id_int = int(order_id) if order_id else None
    except ValueError:
        return RedirectResponse(
            url=f"/support?customer_id={customer_id}&error=Order+ID+must+be+a+number",
            status_code=303,
        )

    with get_cursor() as (conn, cur):
        if order_id_int is not None:
            cur.execute(
                "SELECT 1 FROM orders WHERE order_id = %s AND customer_id = %s",
                (order_id_int, customer_id),
            )
            if not cur.fetchone():
                return RedirectResponse(
                    url=f"/support?customer_id={customer_id}&error=That+order+ID+does+not+belong+to+this+customer",
                    status_code=303,
                )
        cur.execute(
            "INSERT INTO support_tickets (customer_id, order_id, subject, category) "
            "VALUES (%s, %s, %s, %s)",
            (customer_id, order_id_int, subject[:150], category),
        )
    return RedirectResponse(url=f"/support?customer_id={customer_id}", status_code=303)
