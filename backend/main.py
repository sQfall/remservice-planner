from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers import requests, brigades, planning, route_sheets
from services import geocoding_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    # Закрытие HTTP-клиентов при завершении
    await geocoding_service.close_client()


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(requests.router)
app.include_router(brigades.router)
app.include_router(planning.router)
app.include_router(route_sheets.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
