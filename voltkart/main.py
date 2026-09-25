from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes import cart, catalog

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(catalog.router)
app.include_router(cart.router)
