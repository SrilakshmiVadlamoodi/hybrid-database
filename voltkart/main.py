from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="VoltKart")

app.mount("/static", StaticFiles(directory="static"), name="static")
