from datetime import date, datetime
from typing import Any
import traceback
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, distinct, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from pydantic import BaseModel

from database import get_db
from models import (
    DailyPlan,
    RoutePoint,
    RouteSegment,
    ServiceRequest,
    RequestStatus,
    Brigade,
    GarageSegmentType,
)
from schemas import DailyPlanResponse, RoutePointResponse
from services import planning_service, or_tools_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/planning", tags=["planning"])


class ReassignRequest(BaseModel):
    route_point_id: int
    new_brigade_id: int


class PlanDateRequest(BaseModel):
    plan_date: date


BRIGADE_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
    "#8b5cf6", "#06b6d4", "#ec4899", "#f97316",
]


@router.post("/auto")
async def auto_plan(
    plan_date: date = Query(...),
    use_or_tools: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    try:
        if use_or_tools:
            plan = await or_tools_service.ortools_planning(plan_date, db)
        else:
            plan = await planning_service.greedy_planning(plan_date, db)

        # Загружаем route_points для сериализации
        result = await db.execute(
            select(DailyPlan)
            .options(selectinload(DailyPlan.route_points))
            .where(DailyPlan.id == plan.id)
        )
        plan = result.scalar_one()

        return {
            "id": plan.id,
            "plan_date": plan.plan_date.isoformat(),
            "status": plan.status.value if hasattr(plan.status, 'value') else str(plan.status),
            "route_points": [
                {
                    "id": rp.id,
                    "request_id": rp.request_id,
                    "brigade_id": rp.brigade_id,
                    "sequence": rp.sequence,
                    "arrival_time": rp.arrival_time.isoformat() if rp.arrival_time else None,
                    "departure_time": rp.departure_time.isoformat() if rp.departure_time else None,
                }
                for rp in plan.route_points
            ],
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Ошибка при планировании:\n%s", tb)
        print(f"PLANNING ERROR:\n{tb}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))


# Специфичные маршруты ДО общего {plan_date} — иначе FastAPI захватит их как дату
@router.get("/{plan_date}/brigades")
async def get_plan_brigades(plan_date: date, db: AsyncSession = Depends(get_db)):
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(distinct(RoutePoint.brigade_id))
        .join(DailyPlan)
        .where(DailyPlan.plan_date.between(day_start, day_end))
    )
    brigade_ids = [row[0] for row in result.all()]

    if brigade_ids:
        brigades_result = await db.execute(
            select(Brigade)
            .options(joinedload(Brigade.members), joinedload(Brigade.vehicles))
            .where(Brigade.id.in_(brigade_ids))
        )
        brigades = brigades_result.unique().scalars().all()
    else:
        brigades = []

    return brigades


@router.get("/{plan_date}/routes-geometry")
async def get_routes_geometry(plan_date: date, db: AsyncSession = Depends(get_db)):
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.route_points))
        .where(DailyPlan.plan_date.between(day_start, day_end))
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return {"type": "FeatureCollection", "features": []}

    # Загрузить бригады батчем
    brigade_ids = set(rp.brigade_id for rp in plan.route_points)
    brigades_map: dict[int, Brigade] = {}
    if brigade_ids:
        brigades_result = await db.execute(
            select(Brigade).where(Brigade.id.in_(brigade_ids))
        )
        brigades_map = {b.id: b for b in brigades_result.scalars().all()}

    # Загрузить сегменты ТОЛЬКО для текущего плана
    route_point_ids = [rp.id for rp in plan.route_points]
    if route_point_ids:
        segments_result = await db.execute(
            select(RouteSegment).where(
                RouteSegment.geometry_json.isnot(None),
                (RouteSegment.from_point_id.in_(route_point_ids))
                | (RouteSegment.to_point_id.in_(route_point_ids)),
            )
        )
        segments = segments_result.scalars().all()
    else:
        segments = []

    features = []
    for seg in segments:
        bid = None
        if seg.from_point:
            bid = seg.from_point.brigade_id
        elif seg.to_point:
            bid = seg.to_point.brigade_id

        if not bid or bid not in brigades_map:
            continue

        brigade = brigades_map[bid]
        brigade_index = list(brigades_map.keys()).index(bid)
        color = BRIGADE_COLORS[brigade_index % len(BRIGADE_COLORS)]

        geometry = None
        try:
            import json
            geometry = json.loads(seg.geometry_json) if seg.geometry_json else None
        except (json.JSONDecodeError, ValueError):
            geometry = None

        if geometry:
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "brigade_id": bid,
                        "brigade_name": brigade.name,
                        "color": color,
                        "is_garage_segment": seg.is_garage_segment,
                    },
                }
            )

    return {"type": "FeatureCollection", "features": features}


@router.get("/{plan_date}/statistics")
async def get_statistics(plan_date: date, db: AsyncSession = Depends(get_db)):
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.route_points))
        .where(DailyPlan.plan_date.between(day_start, day_end))
        .order_by(DailyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan or not plan.route_points:
        return []

    # Загрузить все бригады одним запросом (N+1 fix)
    brigade_ids = set(rp.brigade_id for rp in plan.route_points)
    brigades_map: dict[int, Brigade] = {}
    if brigade_ids:
        brigades_result = await db.execute(
            select(Brigade).where(Brigade.id.in_(brigade_ids))
        )
        brigades_map = {b.id: b for b in brigades_result.scalars().all()}

    # Группировка по бригадам
    brigade_stats: dict[int, dict[str, Any]] = {}

    for rp in plan.route_points:
        bid = rp.brigade_id
        if bid not in brigade_stats:
            brigade_stats[bid] = {
                "brigade_id": bid,
                "total_requests": 0,
                "total_distance_km": 0.0,
                "total_travel_time_min": 0,
                "overtime_minutes": 0,
                "total_work_time_min": 0,
            }

        brigade_stats[bid]["total_requests"] += 1

        # Время работы
        if rp.arrival_time and rp.departure_time:
            work_min = int((rp.departure_time - rp.arrival_time).total_seconds() / 60)
            brigade_stats[bid]["total_work_time_min"] += work_min

        # Проверка овертайма через загруженную бригаду
        brigade = brigades_map.get(bid)
        if brigade:
            shift_end = datetime.combine(plan_date, brigade.shift_end)
            if rp.departure_time and rp.departure_time > shift_end:
                overtime = int((rp.departure_time - shift_end).total_seconds() / 60)
                brigade_stats[bid]["overtime_minutes"] = max(
                    brigade_stats[bid]["overtime_minutes"], overtime
                )

    # Загрузить сегменты для расстояний и времени перемещения
    segments_result = await db.execute(
        select(RouteSegment).join(
            RoutePoint,
            (RouteSegment.from_point_id == RoutePoint.id) | (RouteSegment.to_point_id == RoutePoint.id),
            isouter=True,
        ).where(RoutePoint.plan_id == plan.id)
    )
    segments = segments_result.unique().scalars().all()

    for seg in segments:
        bid = None
        if seg.from_point and seg.from_point.brigade_id:
            bid = seg.from_point.brigade_id
        elif seg.to_point and seg.to_point.brigade_id:
            bid = seg.to_point.brigade_id

        if bid and bid in brigade_stats:
            brigade_stats[bid]["total_distance_km"] += seg.distance / 1000
            brigade_stats[bid]["total_travel_time_min"] += seg.duration

    # Округлить значения
    for stats in brigade_stats.values():
        stats["total_distance_km"] = round(stats["total_distance_km"], 2)

    return list(brigade_stats.values())


@router.get("/{plan_date}")
async def get_plan(plan_date: date, db: AsyncSession = Depends(get_db)):
    """Получить план на дату с route_points и brigade данными."""
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan)
        .options(
            selectinload(DailyPlan.route_points)
            .selectinload(RoutePoint.request),
        )
        .where(DailyPlan.plan_date.between(day_start, day_end))
        .order_by(DailyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="План на эту дату не найден")

    # Загрузить brigade данные батчем (N+1 fix)
    brigade_ids = set(rp.brigade_id for rp in plan.route_points)
    if brigade_ids:
        brigades_result = await db.execute(
            select(Brigade).where(Brigade.id.in_(brigade_ids))
        )
        brigades_map = {b.id: b for b in brigades_result.scalars().all()}
        for rp in plan.route_points:
            rp.brigade_data = brigades_map.get(rp.brigade_id)

    return plan


@router.put("/reassign")
async def reassign_route_point(
    data: ReassignRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RoutePoint).where(RoutePoint.id == data.route_point_id)
    )
    route_point = result.scalar_one_or_none()
    if not route_point:
        raise HTTPException(status_code=404, detail="Точка маршрута не найдена")

    brigade_result = await db.execute(
        select(Brigade).where(Brigade.id == data.new_brigade_id)
    )
    brigade = brigade_result.scalar_one_or_none()
    if not brigade:
        raise HTTPException(status_code=404, detail="Бригада не найдена")

    route_point.brigade_id = data.new_brigade_id
    await db.commit()
    return {"message": "Точка маршрута переназначена"}


@router.post("/save")
async def save_plan(
    data: PlanDateRequest,
    db: AsyncSession = Depends(get_db),
):
    day_start = datetime.combine(data.plan_date, datetime.min.time())
    day_end = datetime.combine(data.plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan).where(DailyPlan.plan_date.between(day_start, day_end))
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="План не найден")

    plan.status = "confirmed"

    # Обновить статусы заявок
    rp_result = await db.execute(
        select(RoutePoint).where(RoutePoint.plan_id == plan.id)
    )
    route_points = rp_result.scalars().all()
    for rp in route_points:
        req_result = await db.execute(
            select(ServiceRequest).where(ServiceRequest.id == rp.request_id)
        )
        req = req_result.scalar_one_or_none()
        if req:
            req.status = RequestStatus.planned

    await db.commit()
    return {"message": "План сохранён", "plan_id": plan.id}


@router.post("/reset", status_code=204)
async def reset_plan(
    data: PlanDateRequest,
    db: AsyncSession = Depends(get_db),
):
    day_start = datetime.combine(data.plan_date, datetime.min.time())
    day_end = datetime.combine(data.plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.route_points))
        .where(DailyPlan.plan_date.between(day_start, day_end))
        .order_by(DailyPlan.created_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return  # План уже отсутствует — это нормально

    # Удалить сегменты для каждого route_point
    for rp in plan.route_points:
        segments = await db.execute(
            select(RouteSegment).where(
                (RouteSegment.from_point_id == rp.id) | (RouteSegment.to_point_id == rp.id)
            )
        )
        for seg in segments.scalars().all():
            await db.delete(seg)

        # Вернуть заявку в статус "new"
        req = await db.execute(
            select(ServiceRequest).where(ServiceRequest.id == rp.request_id)
        )
        request_obj = req.scalar_one_or_none()
        if request_obj:
            request_obj.status = RequestStatus.new
            # НЕ сбрасываем planned_at — это желаемая дата выполнения

        await db.delete(rp)

    # Удалить оставшиеся сегменты (гаражные без from/to point)
    rp_ids = [rp.id for rp in plan.route_points]
    if rp_ids:
        await db.execute(
            RouteSegment.__table__.delete().where(
                RouteSegment.from_point_id.in_(rp_ids)
                | RouteSegment.to_point_id.in_(rp_ids)
            )
        )

    await db.delete(plan)
    await db.commit()


@router.get("/{plan_date}/routes-geometry")
async def get_routes_geometry(plan_date: date, db: AsyncSession = Depends(get_db)):
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.route_points))
        .where(DailyPlan.plan_date.between(day_start, day_end))
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return {"type": "FeatureCollection", "features": []}

    # Загрузить бригады батчем
    brigade_ids = set(rp.brigade_id for rp in plan.route_points)
    brigades_map: dict[int, Brigade] = {}
    if brigade_ids:
        brigades_result = await db.execute(
            select(Brigade).where(Brigade.id.in_(brigade_ids))
        )
        brigades_map = {b.id: b for b in brigades_result.scalars().all()}

    # Загрузить сегменты ТОЛЬКО для текущего плана (fix: раньше загружал все сегменты в БД)
    route_point_ids = [rp.id for rp in plan.route_points]
    if route_point_ids:
        segments_result = await db.execute(
            select(RouteSegment).where(
                RouteSegment.geometry_json.isnot(None),
                (RouteSegment.from_point_id.in_(route_point_ids))
                | (RouteSegment.to_point_id.in_(route_point_ids)),
            )
        )
        segments = segments_result.scalars().all()
    else:
        segments = []

    features = []
    for seg in segments:
        bid = None
        if seg.from_point:
            bid = seg.from_point.brigade_id
        elif seg.to_point:
            bid = seg.to_point.brigade_id

        if not bid or bid not in brigades_map:
            continue

        brigade = brigades_map[bid]
        brigade_index = list(brigades_map.keys()).index(bid)
        color = BRIGADE_COLORS[brigade_index % len(BRIGADE_COLORS)]

        geometry = None
        try:
            import json
            geometry = json.loads(seg.geometry_json) if seg.geometry_json else None
        except (json.JSONDecodeError, ValueError):
            geometry = None

        if geometry:
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "brigade_id": bid,
                        "brigade_name": brigade.name,
                        "color": color,
                        "is_garage_segment": seg.is_garage_segment,
                    },
                }
            )

    return {"type": "FeatureCollection", "features": features}
