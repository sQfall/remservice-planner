"""
Скрипт для создания 20 тестовых заявок на 2026-04-05 через API.
Запускать при работающем backend: uvicorn main:app
"""
import asyncio
import httpx

BASE_URL = "http://localhost:8000/api"

REQUESTS = [
    # emergency (2)
    {
        "address": "ул. Тверская, д. 1",
        "latitude": 55.756933,
        "longitude": 37.613814,
        "work_type": "electrical",
        "description": "Полное отключение электричества, щиток искрит",
        "priority": "emergency",
        "contact_person": "Смирнов Алексей Петрович",
        "phone": "+7(495)100-01-01",
        "estimated_duration": 90,
        "planned_at": "2026-04-05T08:00:00",
    },
    {
        "address": "Ленинский проспект, д. 15",
        "latitude": 55.705120,
        "longitude": 37.577890,
        "work_type": "plumbing",
        "description": "Прорыв трубы горячей воды, затопление подвала",
        "priority": "emergency",
        "contact_person": "Козлова Мария Ивановна",
        "phone": "+7(495)100-02-02",
        "estimated_duration": 120,
        "planned_at": "2026-04-05T08:00:00",
    },
    # high (4)
    {
        "address": "Новый Арбат, д. 21",
        "latitude": 55.749890,
        "longitude": 37.574540,
        "work_type": "electrical",
        "description": "Искрит розетка в серверной",
        "priority": "high",
        "contact_person": "Иванов Дмитрий Сергеевич",
        "phone": "+7(495)200-03-03",
        "estimated_duration": 60,
        "planned_at": "2026-04-05T09:00:00",
    },
    {
        "address": "Кутузовский проспект, д. 30",
        "latitude": 55.741530,
        "longitude": 37.554670,
        "work_type": "hvac",
        "description": "Не работает отопление в офисе 412",
        "priority": "high",
        "contact_person": "Петрова Елена Владимировна",
        "phone": "+7(495)200-04-04",
        "estimated_duration": 90,
        "planned_at": "2026-04-05T09:30:00",
    },
    {
        "address": "ул. Профсоюзная, д. 45",
        "latitude": 55.671890,
        "longitude": 37.572340,
        "work_type": "plumbing",
        "description": "Засор канализации, обратный поток",
        "priority": "high",
        "contact_person": "Сидоров Олег Николаевич",
        "phone": "+7(495)200-05-05",
        "estimated_duration": 75,
        "planned_at": "2026-04-05T10:00:00",
    },
    {
        "address": "ул. Ленинская Слобода, д. 19",
        "latitude": 55.703450,
        "longitude": 37.640120,
        "work_type": "electrical",
        "description": "Выбивает автомат при включении оборудования",
        "priority": "high",
        "contact_person": "Морозова Анна Дмитриевна",
        "phone": "+7(495)200-06-06",
        "estimated_duration": 45,
        "planned_at": "2026-04-05T10:30:00",
    },
    # normal (10)
    {
        "address": "Ленинградский проспект, д. 37",
        "latitude": 55.801527,
        "longitude": 37.530799,
        "work_type": "hvac",
        "description": "Не работает кондиционер в офисе 305",
        "priority": "normal",
        "contact_person": "Петрова Наталья Игоревна",
        "phone": "+7(495)300-07-07",
        "estimated_duration": 60,
        "planned_at": "2026-04-05T08:00:00",
    },
    {
        "address": "ул. Арбат, д. 10",
        "latitude": 55.752220,
        "longitude": 37.598718,
        "work_type": "plumbing",
        "description": "Замена смесителя в туалете",
        "priority": "normal",
        "contact_person": "Кузнецов Виктор Андреевич",
        "phone": "+7(495)300-08-08",
        "estimated_duration": 45,
        "planned_at": "2026-04-05T09:00:00",
    },
    {
        "address": "Проспект Мира, д. 102",
        "latitude": 55.794560,
        "longitude": 37.645230,
        "work_type": "electrical",
        "description": "Замена люминесцентных ламп на LED",
        "priority": "normal",
        "contact_person": "Волкова Татьяна Сергеевна",
        "phone": "+7(495)300-09-09",
        "estimated_duration": 60,
        "planned_at": "2026-04-05T10:00:00",
    },
    {
        "address": "ул. Большая Якиманка, д. 26",
        "latitude": 55.736780,
        "longitude": 37.614560,
        "work_type": "hvac",
        "description": "Чистка вентиляционной системы",
        "priority": "normal",
        "contact_person": "Новиков Игорь Васильевич",
        "phone": "+7(495)300-10-10",
        "estimated_duration": 90,
        "planned_at": "2026-04-05T11:00:00",
    },
    {
        "address": "ул. Щербаковская, д. 53",
        "latitude": 55.784560,
        "longitude": 37.682340,
        "work_type": "plumbing",
        "description": "Установка унитаза",
        "priority": "normal",
        "contact_person": "Лебедева Ольга Петровна",
        "phone": "+7(495)300-11-11",
        "estimated_duration": 75,
        "planned_at": "2026-04-05T11:30:00",
    },
    {
        "address": "Рублёвское шоссе, д. 28",
        "latitude": 55.757890,
        "longitude": 37.438900,
        "work_type": "electrical",
        "description": "Монтаж дополнительных розеток",
        "priority": "normal",
        "contact_person": "Соколов Андрей Михайлович",
        "phone": "+7(495)300-12-12",
        "estimated_duration": 60,
        "planned_at": "2026-04-05T12:00:00",
    },
    {
        "address": "ул. Автозаводская, д. 23",
        "latitude": 55.703450,
        "longitude": 37.670120,
        "work_type": "hvac",
        "description": "Ремонт приточной установки",
        "priority": "normal",
        "contact_person": "Попова Ирина Александровна",
        "phone": "+7(495)300-13-13",
        "estimated_duration": 120,
        "planned_at": "2026-04-05T13:00:00",
    },
    {
        "address": "ул. Крылатские Холмы, д. 30",
        "latitude": 55.763450,
        "longitude": 37.428900,
        "work_type": "plumbing",
        "description": "Замена полотенцесушителя",
        "priority": "normal",
        "contact_person": "Макаров Дмитрий Олегович",
        "phone": "+7(495)300-14-14",
        "estimated_duration": 90,
        "planned_at": "2026-04-05T13:30:00",
    },
    {
        "address": "ул. Академика Королёва, д. 15",
        "latitude": 55.821230,
        "longitude": 37.607890,
        "work_type": "electrical",
        "description": "Подключение ИБП для сервера",
        "priority": "normal",
        "contact_person": "Фёдорова Светлана Викторовна",
        "phone": "+7(495)300-15-15",
        "estimated_duration": 45,
        "planned_at": "2026-04-05T14:00:00",
    },
    {
        "address": "Варшавское шоссе, д. 47",
        "latitude": 55.672340,
        "longitude": 37.634560,
        "work_type": "hvac",
        "description": "Замена фильтра в центральном кондиционере",
        "priority": "normal",
        "contact_person": "Орлов Павел Иванович",
        "phone": "+7(495)300-16-16",
        "estimated_duration": 30,
        "planned_at": "2026-04-05T14:30:00",
    },
    # low (4)
    {
        "address": "ул. Новый Арбат, д. 15",
        "latitude": 55.750760,
        "longitude": 37.584820,
        "work_type": "other",
        "description": "Ремонт входной двери",
        "priority": "low",
        "contact_person": "Волкова Елена Сергеевна",
        "phone": "+7(495)400-17-17",
        "estimated_duration": 120,
        "planned_at": "2026-04-05T09:00:00",
    },
    {
        "address": "ул. Покровка, д. 35",
        "latitude": 55.759120,
        "longitude": 37.644560,
        "work_type": "plumbing",
        "description": "Капает кран на кухне",
        "priority": "low",
        "contact_person": "Белов Роман Андреевич",
        "phone": "+7(495)400-18-18",
        "estimated_duration": 30,
        "planned_at": "2026-04-05T10:00:00",
    },
    {
        "address": "Комсомольский проспект, д. 22",
        "latitude": 55.726780,
        "longitude": 37.583450,
        "work_type": "electrical",
        "description": "Перенести выключатель на 20 см",
        "priority": "low",
        "contact_person": "Тихонова Вера Михайловна",
        "phone": "+7(495)400-19-19",
        "estimated_duration": 30,
        "planned_at": "2026-04-05T15:00:00",
    },
    {
        "address": "ул. Сретенка, д. 9",
        "latitude": 55.768900,
        "longitude": 37.632340,
        "work_type": "hvac",
        "description": "Проверить давление в системе отопления",
        "priority": "low",
        "contact_person": "Громов Артём Владимирович",
        "phone": "+7(495)400-20-20",
        "estimated_duration": 45,
        "planned_at": "2026-04-05T16:00:00",
    },
]


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        created = 0
        failed = 0

        for i, req_data in enumerate(REQUESTS, 1):
            try:
                response = await client.post(
                    f"{BASE_URL}/requests",
                    json=req_data,
                )
                response.raise_for_status()
                created += 1
                print(f"  [{i:2d}/{len(REQUESTS)}] Создана заявка #{response.json()['id']}: {req_data['address']}")
            except httpx.HTTPStatusError as e:
                failed += 1
                print(f"  [{i:2d}/{len(REQUESTS)}] Ошибка {e.response.status_code}: {req_data['address']}")
            except Exception as e:
                failed += 1
                print(f"  [{i:2d}/{len(REQUESTS)}] Ошибка: {e}")

        print(f"\nИтого: создано {created}, ошибок {failed}")


if __name__ == "__main__":
    asyncio.run(main())
