from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from database import get_db
from models import Brigade, BrigadeMember, Vehicle

router = APIRouter(prefix="/api/brigades", tags=["brigades"])


@router.get("/")
async def get_brigades(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Brigade)
        .options(
            joinedload(Brigade.members),
            joinedload(Brigade.vehicles),
        )
        .order_by(Brigade.name)
    )
    brigades = result.unique().scalars().all()
    return brigades


@router.get("/{brigade_id}")
async def get_brigade(brigade_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Brigade)
        .options(
            joinedload(Brigade.members),
            joinedload(Brigade.vehicles),
        )
        .where(Brigade.id == brigade_id)
    )
    brigade = result.unique().scalar_one_or_none()
    if not brigade:
        raise HTTPException(status_code=404, detail="Бригада не найдена")
    return brigade
