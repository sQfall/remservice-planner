from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import (
    DailyPlan,
    RoutePoint,
    RouteSegment,
    Brigade,
    Vehicle,
    ServiceRequest,
    RequestStatus,
)
from services.pdf_service import generate_route_sheet_pdf

router = APIRouter(prefix="/api/route-sheets", tags=["route-sheets"])


@router.get("/{plan_date}")
async def get_route_sheets(plan_date: date, db: AsyncSession = Depends(get_db)):
    """Список бригад с их заявками на дату."""
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    # Получить план на дату
    plan_result = await db.execute(
        select(DailyPlan)
        .options(
            selectinload(DailyPlan.route_points)
            .selectinload(RoutePoint.request)
        )
        .where(DailyPlan.plan_date.between(day_start, day_end))
        .limit(1)
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        return []

    # Получить route_points
    rp_result = await db.execute(
        select(RoutePoint)
        .options(
            selectinload(RoutePoint.request),
        )
        .where(RoutePoint.plan_id == plan.id)
        .order_by(RoutePoint.brigade_id, RoutePoint.sequence)
    )
    route_points = rp_result.scalars().all()

    # Сгруппировать по бригадам
    brigade_data: dict[int, dict[str, Any]] = {}

    for rp in route_points:
        bid = rp.brigade_id
        if bid not in brigade_data:
            brigade_data[bid] = {
                "brigade_id": bid,
                "brigade_name": "",
                "vehicle_plate": "",
                "members": [],
                "route_points": [],
                "total_distance": 0.0,
                "total_duration": 0,
            }

        # Загрузить данные бригады (один раз)
        if not brigade_data[bid]["brigade_name"]:
            brigade_result = await db.execute(
                select(Brigade)
                .options(
                    selectinload(Brigade.members),
                    selectinload(Brigade.vehicles),
                )
                .where(Brigade.id == bid)
            )
            brigade = brigade_result.scalar_one_or_none()
            if brigade:
                brigade_data[bid]["brigade_name"] = brigade.name
                brigade_data[bid]["members"] = [
                    {"full_name": m.full_name, "role": m.role}
                    for m in brigade.members
                ]
                if brigade.vehicles:
                    v = brigade.vehicles[0]
                    brigade_data[bid]["vehicle_plate"] = v.plate
                    brigade_data[bid]["vehicle_type"] = v.vehicle_type

        # Добавить точку маршрута
        req = rp.request
        brigade_data[bid]["route_points"].append({
            "sequence": rp.sequence,
            "arrival_time": rp.arrival_time.isoformat() if rp.arrival_time else None,
            "departure_time": rp.departure_time.isoformat() if rp.departure_time else None,
            "request": {
                "address": req.address,
                "contact_person": req.contact_person,
                "phone": req.phone,
                "work_type": req.work_type.value if req.work_type else "",
                "description": req.description,
                "estimated_duration": req.estimated_duration,
            },
        })

    # Подсчитать total_distance и total_duration по сегментам
    seg_result = await db.execute(
        select(RouteSegment).join(
            RoutePoint,
            (RouteSegment.from_point_id == RoutePoint.id) | (RouteSegment.to_point_id == RoutePoint.id),
            isouter=True,
        ).where(RoutePoint.plan_id == plan.id)
    )
    segments = seg_result.unique().scalars().all()

    for seg in segments:
        bid = None
        if seg.from_point:
            bid = seg.from_point.brigade_id
        elif seg.to_point:
            bid = seg.to_point.brigade_id

        if bid and bid in brigade_data:
            brigade_data[bid]["total_distance"] += seg.distance
            brigade_data[bid]["total_duration"] += seg.duration

    # Добавляем статус плана в ответ, чтобы фронтенд мог показать "Листы выданы"
    result_data = list(brigade_data.values())
    result_data.append({"_plan_status": plan.status.value if hasattr(plan.status, 'value') else str(plan.status)})
    return result_data


@router.get("/{plan_date}/{brigade_id}/pdf")
async def get_route_sheet_pdf(
    plan_date: date,
    brigade_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Генерировать PDF маршрутного листа для бригады."""
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    # Получить план
    plan_result = await db.execute(
        select(DailyPlan).where(DailyPlan.plan_date.between(day_start, day_end))
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="План на дату не найден")

    # Получить route_points бригады
    rp_result = await db.execute(
        select(RoutePoint)
        .options(selectinload(RoutePoint.request))
        .where(RoutePoint.plan_id == plan.id)
        .where(RoutePoint.brigade_id == brigade_id)
        .order_by(RoutePoint.sequence)
    )
    route_points = rp_result.scalars().all()

    if not route_points:
        raise HTTPException(status_code=404, detail="Маршрут для бригады не найден")

    # Данные бригады
    brigade_result = await db.execute(
        select(Brigade)
        .options(selectinload(Brigade.members), selectinload(Brigade.vehicles))
        .where(Brigade.id == brigade_id)
    )
    brigade = brigade_result.scalar_one_or_none()

    if not brigade:
        raise HTTPException(status_code=404, detail="Бригада не найдена")

    vehicle_plate = ""
    vehicle_type = ""
    if brigade.vehicles:
        v = brigade.vehicles[0]
        vehicle_plate = v.plate
        vehicle_type = v.vehicle_type

    # Подсчитать totals одним запросом (N+1 fix)
    total_distance = 0.0
    total_duration = 0
    if route_points:
        route_point_ids = [rp.id for rp in route_points]
        seg_result = await db.execute(
            select(RouteSegment).where(
                (RouteSegment.from_point_id.in_(route_point_ids))
                | (RouteSegment.to_point_id.in_(route_point_ids))
            )
        )
        for seg in seg_result.scalars().all():
            total_distance += seg.distance
            total_duration += seg.duration

    # Подготовить данные для PDF
    brigade_data = {
        "date": plan_date,
        "brigade_name": brigade.name,
        "specialization": brigade.specialization.value if brigade.specialization else "",
        "vehicle_plate": vehicle_plate,
        "vehicle_type": vehicle_type,
        "members": [
            {"full_name": m.full_name, "role": m.role}
            for m in brigade.members
        ],
        "route_points": [
            {
                "sequence": rp.sequence,
                "arrival_time": rp.arrival_time,
                "departure_time": rp.departure_time,
                "address": rp.request.address,
                "contact_person": rp.request.contact_person,
                "phone": rp.request.phone,
                "work_type": rp.request.work_type.value if rp.request.work_type else "",
                "description": rp.request.description,
                "estimated_duration": rp.request.estimated_duration,
            }
            for rp in route_points
        ],
        "total_distance": total_distance,
        "total_duration": total_duration,
    }

    pdf_bytes = generate_route_sheet_pdf(brigade_data)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=route_sheet_{brigade_id}_{plan_date.isoformat()}.pdf",
        },
    )


@router.post("/{plan_date}/issue")
async def issue_route_sheets(
    plan_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Статус плана → 'active', статусы заявок → 'issued'."""
    day_start = datetime.combine(plan_date, datetime.min.time())
    day_end = datetime.combine(plan_date, datetime.max.time())

    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.route_points))
        .where(DailyPlan.plan_date.between(day_start, day_end))
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="План не найден")

    # Меняем статус плана на active
    plan.status = "active"

    # Меняем статус всех связанных заявок на issued
    for rp in plan.route_points:
        req_result = await db.execute(
            select(ServiceRequest).where(ServiceRequest.id == rp.request_id)
        )
        req = req_result.scalar_one_or_none()
        if req and req.status == RequestStatus.planned:
            req.status = RequestStatus.issued

    await db.commit()

    return {"message": "Маршрутные листы выданы", "plan_id": plan.id}
