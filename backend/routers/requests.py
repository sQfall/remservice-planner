from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import date, datetime
from database import get_db
from models import ServiceRequest, WorkType, Priority, RequestStatus, RoutePoint, RouteSegment
from schemas import (
    ServiceRequestCreate,
    ServiceRequestUpdate,
    ServiceRequestResponse,
)
from services.geocoding_service import geocode_address

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.get("/", response_model=list[ServiceRequestResponse])
async def get_requests(
    db: AsyncSession = Depends(get_db),
    request_date: date | None = Query(None, alias="date"),
    status: RequestStatus | None = Query(None),
    work_type: WorkType | None = Query(None),
    priority: Priority | None = Query(None),
):
    query = (
        select(ServiceRequest)
        .options(selectinload(ServiceRequest.route_point))
    )

    if request_date:
        day_start = datetime.combine(request_date, datetime.min.time())
        day_end = datetime.combine(request_date, datetime.max.time())
        query = query.where(ServiceRequest.planned_at.between(day_start, day_end))
    if status:
        query = query.where(ServiceRequest.status == status)
    if work_type:
        query = query.where(ServiceRequest.work_type == work_type)
    if priority:
        query = query.where(ServiceRequest.priority == priority)

    result = await db.execute(query)
    requests = result.scalars().all()
    return list(requests)


@router.get("/{request_id}", response_model=ServiceRequestResponse)
async def get_request(request_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceRequest)
        .options(selectinload(ServiceRequest.route_point))
        .where(ServiceRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return request


@router.post("/", response_model=ServiceRequestResponse, status_code=201)
async def create_request(
    data: ServiceRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    latitude = data.latitude
    longitude = data.longitude

    if latitude is None or longitude is None or (latitude == 0 and longitude == 0):
        coords = await geocode_address(data.address)
        if coords:
            latitude, longitude = coords

    # Валидация enum-значений
    try:
        work_type = WorkType(data.work_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Недопустимый тип работ: {data.work_type}")

    try:
        priority = Priority(data.priority)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Недопустимый приоритет: {data.priority}")

    request = ServiceRequest(
        address=data.address,
        latitude=latitude or 0.0,
        longitude=longitude or 0.0,
        work_type=work_type,
        description=data.description,
        priority=priority,
        contact_person=data.contact_person,
        phone=data.phone,
        estimated_duration=data.estimated_duration,
        planned_at=data.planned_at,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


@router.put("/{request_id}", response_model=ServiceRequestResponse)
async def update_request(
    request_id: int,
    data: ServiceRequestUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceRequest).where(ServiceRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # Запрет на редактирование запланированных заявок
    if request.status == RequestStatus.planned:
        raise HTTPException(status_code=403, detail="Нельзя редактировать запланированную заявку")

    # Whitelist — не позволяем менять status/planned_at/completed_at/created_at через update
    ALLOWED_FIELDS = {
        "address", "latitude", "longitude", "work_type", "description",
        "priority", "contact_person", "phone", "estimated_duration",
    }
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if k in ALLOWED_FIELDS}
    for key, value in update_data.items():
        setattr(request, key, value)

    await db.commit()
    await db.refresh(request)
    return request


@router.delete("/{request_id}", status_code=204)
async def delete_request(request_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceRequest)
        .options(selectinload(ServiceRequest.route_point))
        .where(ServiceRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # Запрет на удаление запланированных заявок
    if request.status == RequestStatus.planned:
        raise HTTPException(status_code=403, detail="Нельзя удалить запланированную заявку")

    if request.route_point:
        rp = request.route_point
        segments_to_delete = await db.execute(
            select(RouteSegment).where(
                (RouteSegment.from_point_id == rp.id) | (RouteSegment.to_point_id == rp.id)
            )
        )
        for segment in segments_to_delete.scalars().all():
            await db.delete(segment)
        await db.delete(rp)

    await db.delete(request)
    await db.commit()
