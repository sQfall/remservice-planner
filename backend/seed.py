"""
Seed-скрипт для наполнения БД тестовыми данными.
Идемпотентный — безопасно запускать повторно.
"""
import asyncio
from datetime import time, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, init_db
from models import (
    Brigade,
    BrigadeMember,
    Specialization,
    Vehicle,
    ServiceRequest,
    WorkType,
    Priority,
    RequestStatus,
)


async def seed():
    async with AsyncSessionLocal() as db:
        await _seed_brigades(db)
        await _seed_requests(db)
        print("Seed completed successfully.")


async def _seed_brigades(db: AsyncSession):
    """Создать 4 бригады с членами и автомобилями."""
    brigades_data = [
        {
            "name": "Бригада электромонтажников",
            "specialization": Specialization.electrical,
            "garage_lat": 55.751244,
            "garage_lon": 37.618423,  # Центр
            "members": [
                ("Иванов Иван Иванович", "Электромонтёр"),
                ("Петров Пётр Петрович", "Электрик"),
            ],
            "plate": "А001АА 77",
            "vehicle_type": "ГАЗель",
        },
        {
            "name": "Бригада сантехников",
            "specialization": Specialization.plumbing,
            "garage_lat": 55.796127,
            "garage_lon": 37.538186,  # СЗАО
            "members": [
                ("Сидоров Алексей Васильевич", "Сантехник"),
                ("Козлов Дмитрий Николаевич", "Слесарь"),
            ],
            "plate": "В002ВВ 77",
            "vehicle_type": "ГАЗель",
        },
        {
            "name": "Бригада вентиляции",
            "specialization": Specialization.hvac,
            "garage_lat": 55.732744,
            "garage_lon": 37.743916,  # ЮВАО
            "members": [
                ("Морозов Сергей Андреевич", "Вентиляционщик"),
                ("Волков Артём Олегович", "Монтажник"),
                ("Новиков Павел Иванович", "Мастер"),
            ],
            "plate": "Е003ЕЕ 77",
            "vehicle_type": "Газель Next",
        },
        {
            "name": "Универсальная бригада",
            "specialization": Specialization.general,
            "garage_lat": 55.820697,
            "garage_lon": 37.650060,  # СВАО
            "members": [
                ("Кузнецов Олег Дмитриевич", "Мастер-универсал"),
                ("Смирнова Анна Сергеевна", "Техник"),
            ],
            "plate": "К004КК 77",
            "vehicle_type": "Ford Transit",
        },
    ]

    shift_start = time(8, 0)
    shift_end = time(18, 0)

    for data in brigades_data:
        # Проверить существование
        result = await db.execute(select(Brigade).where(Brigade.name == data["name"]))
        if result.scalar_one_or_none():
            print(f"  Бригада '{data['name']}' уже существует — пропускаем")
            continue

        brigade = Brigade(
            name=data["name"],
            specialization=data["specialization"],
            shift_start=shift_start,
            shift_end=shift_end,
            garage_latitude=data["garage_lat"],
            garage_longitude=data["garage_lon"],
        )
        db.add(brigade)
        await db.flush()

        for full_name, role in data["members"]:
            member = BrigadeMember(brigade_id=brigade.id, full_name=full_name, role=role)
            db.add(member)

        vehicle = Vehicle(
            brigade_id=brigade.id,
            plate=data["plate"],
            vehicle_type=data["vehicle_type"],
            year=2023,
        )
        db.add(vehicle)

    await db.commit()


async def _seed_requests(db: AsyncSession):
    """Создать 5 тестовых заявок на сегодня."""
    today = datetime.utcnow().date()
    plan_date_start = datetime.combine(today, datetime.min.time())
    plan_date_end = datetime.combine(today, datetime.max.time())

    result = await db.execute(
        select(ServiceRequest).where(
            ServiceRequest.planned_at.between(plan_date_start, plan_date_end)
        )
    )
    existing = result.scalars().all()

    if existing:
        print(f"  Заявки на {today} уже существуют ({len(existing)} шт.) — пропускаем")
        return

    requests_data = [
        {
            "address": "ул. Тверская, д. 1",
            "lat": 55.756933,
            "lon": 37.613814,
            "work_type": WorkType.electrical,
            "description": "Не работает освещение в коридоре",
            "priority": Priority.high,
            "contact_person": "Смирнова Ольга",
            "phone": "+7(495)123-45-67",
            "estimated_duration": 90,
        },
        {
            "address": "ул. Арбат, д. 10",
            "lat": 55.752220,
            "lon": 37.598718,
            "work_type": WorkType.plumbing,
            "description": "Протечка трубы горячего водоснабжения",
            "priority": Priority.emergency,
            "contact_person": "Козлов Андрей",
            "phone": "+7(495)987-65-43",
            "estimated_duration": 120,
        },
        {
            "address": "Ленинградский проспект, д. 37",
            "lat": 55.801527,
            "lon": 37.530799,
            "work_type": WorkType.hvac,
            "description": "Не работает кондиционер в офисе 305",
            "priority": Priority.medium,
            "contact_person": "Петрова Наталья",
            "phone": "+7(495)555-12-34",
            "estimated_duration": 60,
        },
        {
            "address": "Новый Арбат, д. 21",
            "lat": 55.749890,
            "lon": 37.574540,
            "work_type": WorkType.electrical,
            "description": "Искрит розетка в серверной",
            "priority": Priority.emergency,
            "contact_person": "Иванов Дмитрий",
            "phone": "+7(495)111-22-33",
            "estimated_duration": 45,
        },
        {
            "address": "ул. Новый Арбат, д. 15",
            "lat": 55.750760,
            "lon": 37.584820,
            "work_type": WorkType.general,
            "description": "Ремонт входной двери",
            "priority": Priority.low,
            "contact_person": "Волкова Елена",
            "phone": "+7(495)444-55-66",
            "estimated_duration": 180,
        },
    ]

    base_time = datetime.combine(today, time(9, 0))
    for i, data in enumerate(requests_data):
        req = ServiceRequest(
            address=data["address"],
            latitude=data["lat"],
            longitude=data["lon"],
            work_type=data["work_type"],
            description=data["description"],
            priority=data["priority"],
            status=RequestStatus.new,
            created_at=datetime.utcnow(),
            planned_at=base_time + timedelta(hours=i),
            contact_person=data["contact_person"],
            phone=data["phone"],
            estimated_duration=data["estimated_duration"],
        )
        db.add(req)

    await db.commit()
    print(f"  Создано {len(requests_data)} заявок на {today}")


if __name__ == "__main__":
    asyncio.run(init_db())
    asyncio.run(seed())
