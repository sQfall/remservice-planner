from contextlib import asynccontextmanager
from datetime import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db, AsyncSessionLocal
from models.brigade import Brigade, Specialization
from routers import requests, brigades, planning, route_sheets
from services import geocoding_service


DEFAULT_BRIGADES = [
    {
        "name": "Бригада №1",
        "specialization": Specialization.electrical,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
    },
    {
        "name": "Бригада №2",
        "specialization": Specialization.plumbing,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
    },
    {
        "name": "Бригада №3",
        "specialization": Specialization.hvac,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
    },
    {
        "name": "Бригада №4",
        "specialization": Specialization.general,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
    },
]


async def seed_default_brigades():
    """Создаёт 4 бригады по умолчанию, если их нет"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Brigade))
        existing_brigades = result.scalars().all()

        if len(existing_brigades) == 0:
            for brigade_data in DEFAULT_BRIGADES:
                brigade = Brigade(**brigade_data)
                session.add(brigade)
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_default_brigades()
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
