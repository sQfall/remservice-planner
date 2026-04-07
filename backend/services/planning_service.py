import logging
from datetime import date, datetime, timedelta
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
)
from services.osrm_service import OSRMService, _haversine_distance

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {
    Priority.emergency: 0,
    Priority.high: 1,
    Priority.medium: 2,
    Priority.low: 3,
}


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return _haversine_distance(lat1, lon1, lat2, lon2)


def _nearest_neighbor_order(
    requests: list[ServiceRequest],
    start_coords: tuple[float, float],  # (lat, lon)
) -> list[ServiceRequest]:
    """Упорядочить заявки методом nearest neighbor."""
    if not requests:
        return []

    remaining = list(requests)
    ordered: list[ServiceRequest] = []
    current_lat, current_lon = start_coords

    while remaining:
        nearest = min(
            remaining,
            key=lambda r: _haversine_distance_m(current_lat, current_lon, r.latitude, r.longitude),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current_lat, current_lon = nearest.latitude, nearest.longitude

    return ordered


def _is_brigade_compatible(brigade: Brigade, work_type: str) -> bool:
    """Проверить совместимость бригады с типом работ."""
    return brigade.specialization.value == work_type or brigade.specialization.value == "universal"


async def greedy_planning(plan_date: date, db: AsyncSession, shift_limit_enabled: bool = False) -> DailyPlan:
    """Жадный алгоритм планирования маршрутов на день.

    Args:
        plan_date: дата планирования
        db: сессия БД
        shift_limit_enabled: если True — заявки, не влезающие в смену+60мин,
            остаются в статусе 'new'. Иначе — все заявки назначаются с овертаймом.
    """
    osrm = OSRMService()

    # 1. Получить все новые заявки на plan_date
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(ServiceRequest)
        .where(ServiceRequest.status == RequestStatus.new)
        .where(ServiceRequest.planned_at.between(day_start, day_end))
        .order_by(ServiceRequest.priority)
    )
    requests = list(result.scalars().all())

    if not requests:
        plan = DailyPlan(plan_date=plan_date, status="draft")
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return plan

    # 2. Сортировать по приоритету
    requests.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))

    # 3. Создать план
    plan = DailyPlan(plan_date=plan_date, status="draft")
    db.add(plan)
    await db.flush()

    # 4. Получить все бригады
    brigades_result = await db.execute(
        select(Brigade).options(selectinload(Brigade.members), selectinload(Brigade.vehicles))
    )
    brigades = list(brigades_result.scalars().all())

    if not brigades:
        logger.warning("Нет доступных бригад для планирования")
        plan.status = "draft"
        await db.commit()
        await db.refresh(plan)
        return plan

    # Список всех пропущенных заявок (не влезли в смену)
    all_skipped: list[ServiceRequest] = []

    # 5. Распределить заявки по бригадам
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

    # 6. Для каждой бригады построить маршрут
    for brigade in brigades:
        assigned_requests = brigade_assignments.get(brigade.id, [])
        if not assigned_requests:
            continue

        # Nearest neighbor от гаража
        garage_coords = (brigade.garage_latitude, brigade.garage_longitude)
        ordered_requests = _nearest_neighbor_order(assigned_requests, garage_coords)

        shift_start_dt = datetime.combine(plan_date, brigade.shift_start)
        shift_end_dt = datetime.combine(plan_date, brigade.shift_end)
        # Лимит смены: конец смены + 60 мин overtime
        shift_limit_dt = shift_end_dt + timedelta(minutes=60)

        current_time = shift_start_dt
        current_coords = garage_coords
        sequence = 1
        previous_point_id: int | None = None

        route_points: list[RoutePoint] = []
        skipped_for_brigade: list[ServiceRequest] = []
        segments_to_create: list[tuple] = []

        # Маршрут: гараж → точка1 → точка2 → ... → гараж
        for i, req in enumerate(ordered_requests):
            # Получить маршрут OSRM
            route_data = await osrm.get_route(
                (current_coords[1], current_coords[0]),  # OSRM: lon, lat
                (req.longitude, req.latitude),
            )

            duration_sec = route_data["duration"] if route_data else 600
            duration_min = max(1, int(duration_sec / 60))

            arrival_time = current_time + timedelta(minutes=duration_min)
            est_duration = req.estimated_duration or 60  # минуты
            departure_time = arrival_time + timedelta(minutes=est_duration)

            # Если включен лимит смены и заявка не влезает — пропускаем
            if shift_limit_enabled:
                print(f"  CHECK brigade={brigade.id} req={req.id} departure={departure_time.strftime('%H:%M')} limit={shift_limit_dt.strftime('%H:%M')} exceeds={departure_time > shift_limit_dt}", flush=True)
                if departure_time > shift_limit_dt:
                    skipped_for_brigade.append(req)
                    logger.info(
                        "Бригада %d: заявка %d пропущена (departure %s > лимит %s)",
                        brigade.id, req.id,
                        departure_time.strftime("%H:%M"), shift_limit_dt.strftime("%H:%M"),
                    )
                    continue

            # Создать RoutePoint
            route_point = RoutePoint(
                request_id=req.id,
                brigade_id=brigade.id,
                plan_id=plan.id,
                sequence=sequence,
                arrival_time=arrival_time,
                departure_time=departure_time,
            )
            route_points.append(route_point)
            db.add(route_point)
            await db.flush()

            # Создать RouteSegment (от предыдущей точки или от гаража)
            is_first = (previous_point_id is None)
            segment = RouteSegment(
                from_point_id=previous_point_id,
                to_point_id=route_point.id,
                duration=duration_min,
                distance=route_data["distance"] if route_data else 0,
                geometry_json=str(route_data["geometry"]) if route_data and route_data.get("geometry") else None,
                is_garage_segment=is_first,
                garage_segment_type=GarageSegmentType.garage_to_first if is_first else None,
            )
            segments_to_create.append((segment, None))
            db.add(segment)

            # Обновить заявку
            req.status = RequestStatus.planned
            req.planned_at = arrival_time

            current_time = departure_time
            current_coords = (req.latitude, req.longitude)
            sequence += 1
            previous_point_id = route_point.id

        # Финальный сегмент: последняя точка → гараж
        if route_points:
            last_req = ordered_requests[-1]
            route_data = await osrm.get_route(
                (last_req.longitude, last_req.latitude),
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
                from_point_id=previous_point_id,
                to_point_id=None,
                duration=duration_min,
                distance=route_data["distance"] if route_data else 0,
                geometry_json=str(route_data["geometry"]) if route_data and route_data.get("geometry") else None,
                is_garage_segment=True,
                garage_segment_type=GarageSegmentType.last_to_garage,
            )
            db.add(final_segment)

        # Добавить пропущенные заявки бригады в общий список
        all_skipped.extend(skipped_for_brigade)

    # 7. Сохранить план
    plan.status = "draft"
    await db.commit()
    await db.refresh(plan)

    # 8. Если включен лимит смены — перенести пропущенные заявки на следующий день
    next_day = plan_date + timedelta(days=1)
    shifted_requests = []
    if shift_limit_enabled and all_skipped:
        for req in all_skipped:
            req.priority = Priority.high
            req.planned_at = datetime.combine(next_day, datetime.min.time()) + timedelta(hours=8)
            shifted_requests.append(req)
            logger.info(
                "Заявка #%d перенесена на %s с приоритетом high",
                req.id, next_day
            )
        await db.commit()

    logger.info(
        "План на %s создан: %d заявок назначено, %d не назначено, %d перенесено на %s",
        plan_date,
        len(requests) - len(unplanned) - len(all_skipped),
        len(unplanned),
        len(shifted_requests),
        next_day,
    )

    return plan
