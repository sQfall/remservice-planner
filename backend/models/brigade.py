from __future__ import annotations
import enum
from datetime import time
from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    from models.route import RoutePoint
    from models.vehicle import Vehicle


class Specialization(str, enum.Enum):
    electrical = "electrical"
    plumbing = "plumbing"
    hvac = "hvac"
    general = "general"


class Brigade(Base):
    __tablename__ = "brigades"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    specialization: Mapped[Specialization] = mapped_column(Enum(Specialization), nullable=False)
    shift_start: Mapped[time] = mapped_column(nullable=False)
    shift_end: Mapped[time] = mapped_column(nullable=False)
    garage_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    garage_longitude: Mapped[float] = mapped_column(Float, nullable=False)

    members: Mapped[list["BrigadeMember"]] = relationship(back_populates="brigade", cascade="all, delete-orphan")
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="brigade", cascade="all, delete-orphan")
    route_points: Mapped[list["RoutePoint"]] = relationship(back_populates="brigade")  # type: ignore[name-defined]


class BrigadeMember(Base):
    __tablename__ = "brigade_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    brigade_id: Mapped[int] = mapped_column(ForeignKey("brigades.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)

    brigade: Mapped["Brigade"] = relationship(back_populates="members")
