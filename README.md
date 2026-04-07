# РемСервис-Планировщик

Автоматизированная система планирования мобильных аварийно-ремонтных бригад. Диспетчер создаёт заявки, система автоматически распределяет их по бригадам с учётом специализации и времени работы, строит маршруты на карте и генерирует маршрутные листы в PDF.

## Возможности

- **Управление заявками** — создание, редактирование, удаление заявок с указанием адреса, типа работ, приоритета и контактных данных
- **Управление бригадами** — просмотр состава бригад, их специализации, транспортных средств и гаражей
- **Автопланирование** — жадный алгоритм распределяет заявки по бригадам, строит оптимальные маршруты с учётом времени работы и переездов (OSRM)
- **Планирование с учётом смены** — заявки, не влезающие в рабочее время бригады, переносятся на следующий день с высоким приоритетом
- **Карта маршрутов** — визуализация маршрутов бригад на интерактивной карте (Leaflet) с детализацией каждого отрезка
- **Маршрутные листы** — просмотр и скачивание PDF-листов для каждой бригады с адресами, временем и контактами
- **Статистика** — время работы, расстояние, количество заявок по каждой бригаде

## Стек технологий

### Backend
| Технология | Версия | Назначение |
|---|---|---|
| Python | 3.11+ | Язык |
| FastAPI | ≥0.109 | REST API |
| SQLAlchemy | ≥2.0 | ORM |
| SQLite | — | База данных |
| ReportLab | ≥4.0 | Генерация PDF |
| httpx | ≥0.26 | HTTP-клиент (геокодирование) |

### Frontend
| Технология | Версия | Назначение |
|---|---|---|
| Vue 3 | ≥3.4 | UI-фреймворк (Composition API) |
| Vite | ≥5.4 | Сборщик |
| Pinia | ≥2.1 | Управление состоянием |
| Vue Router | ≥4.2 | Маршрутизация |
| Axios | ≥1.6 | HTTP-клиент |
| Leaflet | ≥1.9 | Интерактивная карта |

## Требования

- **Python** 3.11 или выше
- **Node.js** 18 или выше
- **npm** (или pnpm/yarn)

## Быстрый запуск

### 1. Клонирование

```bash
git clone https://github.com/your-username/remservice-planner.git
cd remservice-planner
```

### 2. Backend

```bash
cd backend

# Создание виртуального окружения (рекомендуется)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Установка зависимостей
pip install -r requirements.txt

# Запуск сервера разработки
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend запустится на **http://127.0.0.1:8000**

Документация API (Swagger UI): **http://127.0.0.1:8000/docs**

> База данных `data.db` создаётся автоматически при первом запуске.

### 3. Frontend

Откройте новый терминал:

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск сервера разработки
npm run dev
```

Frontend запустится на **http://localhost:5173**

> Vite автоматически проксирует запросы `/api` на backend (порт 8000).

### 4. Открыть приложение

Перейдите на **http://localhost:5173** в браузере.

## Структура проекта

```
remservice-planner/
├── backend/
│   ├── main.py                     # Точка входа FastAPI
│   ├── config.py                   # Настройки (REMSERVICE_*)
│   ├── database.py                 # Async SQLAlchemy
│   ├── requirements.txt            # Зависимости Python
│   ├── data.db                     # SQLite (создаётся автоматически)
│   │
│   ├── models/                     # SQLAlchemy модели
│   │   ├── brigade.py              # Brigade, BrigadeMember
│   │   ├── vehicle.py              # Vehicle
│   │   ├── request.py              # ServiceRequest
│   │   └── route.py                # DailyPlan, RoutePoint, RouteSegment
│   │
│   ├── schemas/                    # Pydantic схемы
│   │   ├── brigade.py
│   │   ├── request.py
│   │   ├── planning.py
│   │   └── route_sheet.py
│   │
│   ├── routers/                    # API эндпоинты
│   │   ├── requests.py             # CRUD заявок
│   │   ├── brigades.py             # Просмотр бригад
│   │   ├── planning.py             # Планирование + статистика + геометрия
│   │   └── route_sheets.py         # Маршрутные листы + PDF
│   │
│   └── services/                   # Бизнес-логика
│       ├── planning_service.py     # Жадный алгоритм планирования
│       ├── osrm_service.py         # OSRM маршруты + haversine fallback
│       ├── geocoding_service.py    # Nominatim геокодирование
│       └── pdf_service.py          # Генерация PDF (ReportLab)
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js              # Прокси /api → localhost:8000
    │
    └── src/
        ├── main.js
        ├── App.vue
        ├── api/index.js            # Axios клиент
        ├── router/index.js         # Vue Router
        ├── stores/                 # Pinia stores
        │   ├── brigades.js
        │   ├── requests.js
        │   └── planning.js
        ├── views/                  # Страницы
        │   ├── RequestsView.vue
        │   ├── BrigadesView.vue
        │   ├── PlanningView.vue
        │   ├── MapView.vue
        │   └── RouteSheetsView.vue
        └── components/
            ├── AppHeader.vue
            ├── MapComponent.vue
            └── TimelineChart.vue
```

## Конфигурация

Все настройки задаются через переменные окружения с префиксом `REMSERVICE_`. Значения по умолчанию подходят для локальной разработки.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `REMSERVICE_APP_NAME` | `РемСервис-Планировщик` | Название приложения |
| `REMSERVICE_DATABASE_URL` | `sqlite+aiosqlite:///./data.db` | Строка подключения к БД |
| `REMSERVICE_DEBUG` | `True` | Включает логирование SQL-запросов |

### Пример использования

**Linux/macOS:**
```bash
export REMSERVICE_DEBUG=false
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Windows (cmd):**
```cmd
set REMSERVICE_DEBUG=false
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Windows (PowerShell):**
```powershell
$env:REMSERVICE_DEBUG="false"
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API

### Заявки
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/requests/` | Список всех заявок |
| GET | `/api/requests/{id}` | Информация о заявке |
| POST | `/api/requests/` | Создание заявки |
| PUT | `/api/requests/{id}` | Обновление заявки |
| DELETE | `/api/requests/{id}` | Удаление заявки |

### Бригады
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/brigades/` | Список бригад |

### Планирование
| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/planning/auto?plan_date=&shift_limit=` | Автопланирование |
| GET | `/api/planning/{date}` | Получить план на дату |
| GET | `/api/planning/{date}/statistics` | Статистика плана |
| GET | `/api/planning/{date}/routes-geometry` | GeoJSON маршрутов для карты |
| POST | `/api/planning/reset` | Сбросить план |

### Маршрутные листы
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/route-sheets/{date}` | Маршрутные листы на дату |
| GET | `/api/route-sheets/{date}/{brigade_id}/pdf` | Скачать PDF листа |
| POST | `/api/route-sheets/{date}/issue` | Выдать листы (статус → active) |

## Деплой

### Render.com (Backend)
1. Подключите GitHub репозиторий к Render
2. Создайте **Web Service** с указанием директории `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Для SQLite используйте внешнее хранилище или подключите PostgreSQL

### Vercel (Frontend)
1. Подключите репозиторий к Vercel
2. Укажите корень проекта как `frontend`
3. В `vite.config.js` измените `proxy.target` на URL вашего backend
4. Deploy — Vercel автоматически соберёт и опубликует приложение

### Railway.app (Всё в одном)
1. Создайте проект в Railway
2. Добавьте сервис для backend (Python)
3. Добавьте сервис для frontend (Node.js)
4. Railway автоматически настроит PostgreSQL и обновит `DATABASE_URL`

## Лицензия

MIT
