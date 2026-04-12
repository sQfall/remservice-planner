from contextlib import asynccontextmanager
from datetime import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db, AsyncSessionLocal
from models.brigade import Brigade, BrigadeMember, Specialization
from models.vehicle import Vehicle
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
        "members": [
            {"full_name": "Иванов Иван Иванович", "role": "Бригадир"},
            {"full_name": "Петров Пётр Петрович", "role": "Электрик"},
            {"full_name": "Сидоров Алексей Николаевич", "role": "Электрик"},
        ],
        "vehicles": [
            {"plate": "А123БВ77", "vehicle_type": "Газель", "year": 2020},
        ],
    },
    {
        "name": "Бригада №2",
        "specialization": Specialization.plumbing,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
        "members": [
            {"full_name": "Козлов Дмитрий Сергеевич", "role": "Бригадир"},
            {"full_name": "Морозов Виктор Андреевич", "role": "Сантехник"},
            {"full_name": "Волков Андрей Игоревич", "role": "Сантехник"},
        ],
        "vehicles": [
            {"plate": "В456ГД77", "vehicle_type": "Лада Ларгус", "year": 2021},
        ],
    },
    {
        "name": "Бригада №3",
        "specialization": Specialization.hvac,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
        "members": [
            {"full_name": "Лебедев Максим Олегович", "role": "Бригадир"},
            {"full_name": "Егоров Сергей Владимирович", "role": "Инженер вентиляции"},
            {"full_name": "Кузнецов Денис Павлович", "role": "Инженер вентиляции"},
        ],
        "vehicles": [
            {"plate": "Е789ЖЗ77", "vehicle_type": "Ford Transit", "year": 2019},
        ],
    },
    {
        "name": "Бригада №4",
        "specialization": Specialization.general,
        "shift_start": time(8, 0),
        "shift_end": time(17, 0),
        "garage_latitude": 55.7558,
        "garage_longitude": 37.6173,
        "members": [
            {"full_name": "Новиков Александр Михайлович", "role": "Бригадир"},
            {"full_name": "Соколов Роман Юрьевич", "role": "Мастер"},
            {"full_name": "Попов Виталий Константинович", "role": "Мастер"},
        ],
        "vehicles": [
            {"plate": "И012КЛ77", "vehicle_type": "УАЗ Профи", "year": 2022},
        ],
    },
]


async def seed_default_brigades():
    """Создаёт 4 бригады по умолчанию с участниками и автомобилями, если их нет"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Brigade))
        existing_brigades = result.scalars().all()

        if len(existing_brigades) == 0:
            for brigade_data in DEFAULT_BRIGADES:
                members_data = brigade_data.pop("members")
                vehicles_data = brigade_data.pop("vehicles")

                brigade = Brigade(**brigade_data)
                session.add(brigade)
                await session.flush()

                for member in members_data:
                    session.add(BrigadeMember(brigade_id=brigade.id, **member))

                for vehicle in vehicles_data:
                    session.add(Vehicle(brigade_id=brigade.id, **vehicle))

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
    allow_origins=settings.cors_origins_list,
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
