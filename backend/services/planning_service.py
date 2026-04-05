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


async def greedy_planning(plan_date: date, db: AsyncSession) -> DailyPlan:
    """Жадный алгоритм планирования маршрутов на день."""
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

        current_time = shift_start_dt
        current_coords = garage_coords
        sequence = 1
        previous_point_id: int | None = None

        route_points: list[RoutePoint] = []
        segments_to_create: list[tuple] = []  # (from_point_id, to_point_id, route_data, is_garage, garage_type)

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

            # Проверка на выход за смену
            if arrival_time > shift_end_dt:
                logger.warning(
                    "Бригада %d: заявка %d выходит за смену (прибытие %s > конец %s)",
                    brigade.id,
                    req.id,
                    arrival_time,
                    shift_end_dt,
                )

            est_duration = req.estimated_duration or 60  # минуты
            departure_time = arrival_time + timedelta(minutes=est_duration)

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
            is_first = i == 0
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

    # 7. Сохранить план
    plan.status = "draft"
    await db.commit()
    await db.refresh(plan)

    if unplanned:
        logger.info("Не назначено заявок: %d", len(unplanned))

    logger.info(
        "План на %s создан: %d заявок назначено, %d не назначено",
        plan_date,
        len(requests) - len(unplanned),
        len(unplanned),
    )

    return plan
