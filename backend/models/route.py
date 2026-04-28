from __future__ import annotations
import enum
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    from models.brigade import Brigade
    from models.request import ServiceRequest


class PlanStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"


class GarageSegmentType(str, enum.Enum):
    garage_to_first = "garage_to_first"
    last_to_garage = "last_to_garage"


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus), nullable=False, default=PlanStatus.draft)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    route_points: Mapped[list["RoutePoint"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class RoutePoint(Base):
    __tablename__ = "route_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.id"), nullable=False)
    brigade_id: Mapped[int] = mapped_column(ForeignKey("brigades.id"), nullable=False)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("daily_plans.id"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    departure_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    request: Mapped["ServiceRequest"] = relationship(back_populates="route_point")
    brigade: Mapped["Brigade"] = relationship(back_populates="route_points")
    plan: Mapped["DailyPlan"] = relationship(back_populates="route_points")

    incoming_segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="to_point",
        foreign_keys="RouteSegment.to_point_id",
    )
    outgoing_segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="from_point",
        foreign_keys="RouteSegment.from_point_id",
    )


class RouteSegment(Base):
    __tablename__ = "route_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_point_id: Mapped[int | None] = mapped_column(ForeignKey("route_points.id"), nullable=True)
    to_point_id: Mapped[int | None] = mapped_column(ForeignKey("route_points.id"), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # минуты
    distance: Mapped[float] = mapped_column(Float, nullable=False)  # метры
    geometry_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_garage_segment: Mapped[bool] = mapped_column(nullable=False, default=False)
    garage_segment_type: Mapped[GarageSegmentType | None] = mapped_column(Enum(GarageSegmentType), nullable=True)

    from_point: Mapped["RoutePoint | None"] = relationship(
        back_populates="outgoing_segments",
        foreign_keys=[from_point_id],
    )
    to_point: Mapped["RoutePoint | None"] = relationship(
        back_populates="incoming_segments",
        foreign_keys=[to_point_id],
    )
