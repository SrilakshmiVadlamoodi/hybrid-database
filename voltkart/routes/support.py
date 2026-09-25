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
        request,
        "support.html",
        {
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
