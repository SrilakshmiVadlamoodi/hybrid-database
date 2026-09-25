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
