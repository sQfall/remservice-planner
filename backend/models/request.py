from __future__ import annotations
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    from models.route import RoutePoint


class WorkType(str, enum.Enum):
    electrical = "electrical"
    plumbing = "plumbing"
    hvac = "hvac"
    structural = "structural"
    general = "general"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    emergency = "emergency"


class RequestStatus(str, enum.Enum):
    new = "new"
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    work_type: Mapped[WorkType] = mapped_column(Enum(WorkType), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), nullable=False, default=Priority.medium)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), nullable=False, default=RequestStatus.new)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)

    route_point: Mapped["RoutePoint | None"] = relationship(back_populates="request")
