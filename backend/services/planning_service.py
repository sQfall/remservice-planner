import json
import logging
from datetime import date, datetime, timedelta, time as dt_time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import (
    ServiceRequest,
    RequestStatus,
    Priority,
    Brigade,
    DailyPlan,
    RoutePoint,
    RouteSegment,
    GarageSegmentType,
    PlanStatus,
)
from services.osrm_service import OSRMService, _haversine_distance

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    Priority.emergency: 0,
    Priority.high: 1,
    Priority.medium: 2,
    Priority.low: 3,
}


def _nearest_neighbor_order(
    requests: list[ServiceRequest],
    start_coords: tuple[float, float],  # (lat, lon)
) -> list[ServiceRequest]:
    """Упорядочить заявки методом nearest neighbor.

    Заявки с временными окнами получают приоритет и сортируются по
    времени начала окна, затем nearest neighbor применяется внутри групп.
    """
    if not requests:
        return []

    # Разделяем: с окнами и без
    with_windows = [r for r in requests if r.time_window_start is not None and r.time_window_end is not None]
    without_windows = [r for r in requests if r.time_window_start is None or r.time_window_end is None]

    # Сортируем с окнами по времени начала окна
    with_windows.sort(key=lambda r: r.time_window_start)

    # Для каждой группы применяем nearest neighbor
    ordered: list[ServiceRequest] = []
    current_lat, current_lon = start_coords

    # Сначала заявки с окнами —nearest neighbor, но respecting window order
    remaining = list(with_windows)
    while remaining:
        # Выбираем ближайшую из допустимых (по порядку окон)
        nearest_idx = min(
            range(len(remaining)),
            key=lambda i: _haversine_distance(
                current_lat, current_lon,
                remaining[i].latitude, remaining[i].longitude
            ),
        )
        nearest = remaining[nearest_idx]
        ordered.append(nearest)
        remaining.pop(nearest_idx)
        current_lat, current_lon = nearest.latitude, nearest.longitude

    # Теперь заявки без окон — чистый nearest neighbor
    remaining = list(without_windows)
    while remaining:
        nearest_idx = min(
            range(len(remaining)),
            key=lambda i: _haversine_distance(
                current_lat, current_lon,
                remaining[i].latitude, remaining[i].longitude
            ),
        )
        nearest = remaining[nearest_idx]
        ordered.append(nearest)
        remaining.pop(nearest_idx)
        current_lat, current_lon = nearest.latitude, nearest.longitude

    return ordered


def _is_brigade_available_at(brigade: Brigade, check_time: datetime) -> bool:
    """Проверить, что бригада работает в указанное время."""
    shift_start = datetime.combine(check_time.date(), brigade.shift_start)
    shift_end = datetime.combine(check_time.date(), brigade.shift_end)
    return shift_start <= check_time <= shift_end


def _is_brigade_compatible(brigade: Brigade, work_type: str) -> bool:
    """Проверить совместимость бригады с типом работ."""
    return brigade.specialization.value == work_type or brigade.specialization.value == "universal"


def _check_time_window(
    arrival_time: datetime,
    request: ServiceRequest,
    brigade: Brigade,
) -> tuple[datetime, bool, str]:
    """Проверить и скорректировать время начала работ с учётом временного окна и смены бригады.

    Returns:
        (actual_start_time, is_feasible, reason)
        - Если окна нет — возвращаем arrival_time и True.
        - Если окно есть:
            - arrival_time < window_start: ждём до window_start (если window_start в смене) → True
            - arrival_time внутри окна: начинаем сразу → True
            - arrival_time > window_end: → False (конфликт)
            - window_start или window_end вне смены бригады: → False
    """
    # Проверяем смену бригады
    shift_start = datetime.combine(arrival_time.date(), brigade.shift_start)
    shift_end = datetime.combine(arrival_time.date(), brigade.shift_end)

    if arrival_time < shift_start:
        arrival_time = shift_start

    if request.time_window_start is None or request.time_window_end is None:
        return arrival_time, True, ""

    # Преобразуем время окна в datetime на тот же день
    window_start = datetime.combine(arrival_time.date(), request.time_window_start)
    window_end = datetime.combine(arrival_time.date(), request.time_window_end)

    # Проверяем, что окно попадает в смену бригады
    if window_start < shift_start or window_end > shift_end:
        return arrival_time, False, f"окно ({request.time_window_start.strftime('%H:%M')}-{request.time_window_end.strftime('%H:%M')}) вне смены бригады"

    if arrival_time < window_start:
        # Бригада приехала раньше — ждёт начала окна
        return window_start, True, "ожидание начала окна"

    if arrival_time > window_end:
        # Бригада не успевает в временное окно — конфликт
        return arrival_time, False, f"прибытие {arrival_time.strftime('%H:%M')} > конец окна {window_end.strftime('%H:%M')}"

    # Внутри окна — начинаем сразу
    return arrival_time, True, "внутри окна"


async def _load_pending_requests(plan_date: date, db: AsyncSession) -> list[ServiceRequest]:
    """Загрузить новые заявки на указанную дату."""
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(ServiceRequest)
        .where(ServiceRequest.status == RequestStatus.new)
        .where(ServiceRequest.planned_at.between(day_start, day_end))
        .order_by(ServiceRequest.priority)
    )
    requests = list(result.scalars().all())
    requests.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))
    return requests


async def _create_plan(plan_date: date, db: AsyncSession) -> DailyPlan:
    """Создать новый ежедневный план."""
    plan = DailyPlan(plan_date=plan_date, status=PlanStatus.draft)
    db.add(plan)
    await db.flush()
    return plan


async def _load_brigades(db: AsyncSession) -> list[Brigade]:
    """Загрузить все бригады с сотрудниками и транспортом."""
    brigades_result = await db.execute(
        select(Brigade).options(selectinload(Brigade.members), selectinload(Brigade.vehicles))
    )
    return list(brigades_result.scalars().all())


def _assign_requests_to_brigades(
    requests: list[ServiceRequest],
    brigades: list[Brigade],
) -> tuple[dict[int, list[ServiceRequest]], list[ServiceRequest]]:
    """Распределить заявки по бригадам."""
    brigade_assignments: dict[int, list[ServiceRequest]] = {b.id: [] for b in brigades}
    unplanned: list[ServiceRequest] = []

    for req in requests:
        assigned = False
        for brigade in brigades:
            if _is_brigade_compatible(brigade, req.work_type.value):
                brigade_assignments[brigade.id].append(req)
                assigned = True
                break

        if not assigned:
            unplanned.append(req)
            logger.warning(
                "Заявка %d (тип=%s) не назначена — нет совместимых бригад",
                req.id,
                req.work_type.value,
            )

    return brigade_assignments, unplanned


async def _build_brigade_route(
    brigade: Brigade,
    assigned_requests: list[ServiceRequest],
    plan: DailyPlan,
    plan_date: date,
    db: AsyncSession,
    osrm: OSRMService,
    shift_limit_enabled: bool,
) -> list[ServiceRequest]:
    """Построить маршрут для одной бригады. Возвращает список пропущенных заявок."""
    if not assigned_requests:
        return []

    garage_coords = (brigade.garage_latitude, brigade.garage_longitude)
    ordered_requests = _nearest_neighbor_order(assigned_requests, garage_coords)

    shift_start_dt = datetime.combine(plan_date, brigade.shift_start)
    shift_end_dt = datetime.combine(plan_date, brigade.shift_end)
    shift_limit_dt = shift_end_dt + timedelta(minutes=60)

    current_time = shift_start_dt
    current_coords: tuple[float, float] = garage_coords
    sequence = 1
    previous_route_point: RoutePoint | None = None

    skipped_for_brigade: list[ServiceRequest] = []

    for req in ordered_requests:
        route_data = await osrm.get_route(
            (current_coords[1], current_coords[0]),  # OSRM: lon, lat
            (req.longitude, req.latitude),
        )

        duration_sec = route_data["duration"] if route_data else 600
        duration_min = max(1, int(duration_sec / 60))

        raw_arrival_time = current_time + timedelta(minutes=duration_min)

        # Проверяем временное окно и смену бригады
        actual_start, is_feasible, reason = _check_time_window(raw_arrival_time, req, brigade)

        if not is_feasible:
            # Заявка не влезает в временное окно или вне смены — пропускаем
            skipped_for_brigade.append(req)
            logger.info(
                "Бригада %d: заявка %d пропущена — %s",
                brigade.id, req.id, reason,
            )
            continue

        arrival_time = actual_start
        est_duration = req.estimated_duration or 60
        departure_time = arrival_time + timedelta(minutes=est_duration)

        if shift_limit_enabled and departure_time > shift_limit_dt:
            skipped_for_brigade.append(req)
            logger.info(
                "Бригада %d: заявка %d пропущена (departure %s > лимит %s)",
                brigade.id, req.id,
                departure_time.strftime("%H:%M"), shift_limit_dt.strftime("%H:%M"),
            )
            continue

        route_point = RoutePoint(
            request_id=req.id,
            brigade_id=brigade.id,
            plan_id=plan.id,
            sequence=sequence,
            arrival_time=arrival_time,
            departure_time=departure_time,
        )
        db.add(route_point)

        is_first = (previous_route_point is None)
        segment = RouteSegment(
            from_point=previous_route_point,
            to_point=route_point,
            duration=duration_min,
            distance=route_data["distance"] if route_data else 0,
            geometry_json=json.dumps(route_data["geometry"]) if route_data and route_data.get("geometry") else None,
            is_garage_segment=is_first,
            garage_segment_type=GarageSegmentType.garage_to_first if is_first else None,
        )
        db.add(segment)

        req.status = RequestStatus.planned
        # planned_at не трогаем — реальное время хранится в route_point.arrival_time

        current_time = departure_time
        current_coords = (req.latitude, req.longitude)
        sequence += 1
        previous_route_point = route_point

    # Финальный сегмент: последняя точка → гараж
    # FIX #1: используем current_coords (реальная последняя точка), а не ordered_requests[-1]
    if previous_route_point is not None:
        route_data = await osrm.get_route(
            (current_coords[1], current_coords[0]),  # lon, lat для OSRM
            (brigade.garage_longitude, brigade.garage_latitude),
        )

        duration_sec = route_data["duration"] if route_data else 600
        duration_min = max(1, int(duration_sec / 60))

        arrival_at_garage = current_time + timedelta(minutes=duration_min)

        if arrival_at_garage > shift_end_dt:
            logger.warning(
                "Бригада %d: возвращение в гараж выходит за смену (%s > %s)",
                brigade.id,
                arrival_at_garage,
                shift_end_dt,
            )

        final_segment = RouteSegment(
            from_point=previous_route_point,
            to_point_id=None,
            duration=duration_min,
            distance=route_data["distance"] if route_data else 0,
            geometry_json=json.dumps(route_data["geometry"]) if route_data and route_data.get("geometry") else None,
            is_garage_segment=True,
            garage_segment_type=GarageSegmentType.last_to_garage,
        )
        db.add(final_segment)

    # Один flush для всей бригады
    await db.flush()

    return skipped_for_brigade


async def _handle_skipped_requests(
    all_skipped: list[ServiceRequest],
    plan_date: date,
    db: AsyncSession,
    shift_limit_enabled: bool,
) -> list[ServiceRequest]:
    """Обработать пропущенные заявки — перенести на следующий день."""
    next_day = plan_date + timedelta(days=1)
    shifted_requests = []

    if shift_limit_enabled and all_skipped:
        for req in all_skipped:
            req.priority = Priority.high
            req.planned_at = datetime.combine(next_day, datetime.min.time()) + timedelta(hours=8)
            shifted_requests.append(req)
            reason = ""
            if req.time_window_start and req.time_window_end:
                reason = f" (конфликт с окном {req.time_window_start.strftime('%H:%M')}-{req.time_window_end.strftime('%H:%M')})"
            logger.info(
                "Заявка #%d перенесена на %s с приоритетом high%s",
                req.id, next_day, reason,
            )

    return shifted_requests


async def greedy_planning(plan_date: date, db: AsyncSession, shift_limit_enabled: bool = False) -> DailyPlan:
    """Жадный алгоритм планирования маршрутов на день.

    Args:
        plan_date: дата планирования
        db: сессия БД
        shift_limit_enabled: если True — заявки, не влезающие в смену+60мин,
            остаются в статусе 'new'. Иначе — все заявки назначаются с овертаймом.
    """
    osrm = OSRMService()

    # FIX #4: оборачиваем весь алгоритм в try/except/finally для rollback и закрытия клиента
    try:
        # Этап 1: Загрузка данных
        requests = await _load_pending_requests(plan_date, db)

        if not requests:
            plan = await _create_plan(plan_date, db)
            await db.commit()
            await db.refresh(plan)
            return plan

        plan = await _create_plan(plan_date, db)

        brigades = await _load_brigades(db)
        if not brigades:
            logger.warning("Нет доступных бригад для планирования")
            plan.status = PlanStatus.draft
            await db.commit()
            await db.refresh(plan)
            return plan

        # Этап 2: Распределение заявок по бригадам
        brigade_assignments, unplanned = _assign_requests_to_brigades(requests, brigades)

        # Этап 3: Построение маршрутов для каждой бригады
        all_skipped: list[ServiceRequest] = []

        for brigade in brigades:
            assigned_requests = brigade_assignments.get(brigade.id, [])
            skipped = await _build_brigade_route(
                brigade, assigned_requests, plan, plan_date, db, osrm, shift_limit_enabled
            )
            all_skipped.extend(skipped)

        # Этап 4: Обработка пропущенных заявок
        shifted_requests = await _handle_skipped_requests(all_skipped, plan_date, db, shift_limit_enabled)

        # Этап 5: Сохранение плана
        plan.status = PlanStatus.draft
        await db.commit()
        await db.refresh(plan)

        next_day = plan_date + timedelta(days=1)
        logger.info(
            "План на %s создан: %d заявок назначено, %d не назначено, %d перенесено на %s",
            plan_date,
            len(requests) - len(unplanned) - len(all_skipped),
            len(unplanned),
            len(shifted_requests),
            next_day,
        )

        return plan

    except Exception as e:
        await db.rollback()
        logger.error("Ошибка планирования на %s: %s", plan_date, e, exc_info=True)
        raise
    finally:
        await osrm.close()
