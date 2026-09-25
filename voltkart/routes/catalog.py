from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from db import get_cursor
from routes.common import get_all_customers, parse_customer_id
from templates import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, category: str | None = None, customer_id: str | None = None):
    customer_id = parse_customer_id(customer_id)
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
        request,
        "catalog.html",
        {
            "products": products,
            "categories": categories,
            "selected_category": category,
            "customers": customers,
            "customer_id": customer_id,
        },
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(request: Request, product_id: int, customer_id: str | None = None):
    customer_id = parse_customer_id(customer_id)
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
        request,
        "product_detail.html",
        {"product": product, "customers": customers, "customer_id": customer_id},
    )
