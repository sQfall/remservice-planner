from __future__ import annotations
from datetime import time
from pydantic import BaseModel, ConfigDict


class BrigadeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    specialization: str
    shift_start: time
    shift_end: time
    garage_latitude: float
    garage_longitude: float


class BrigadeCreate(BrigadeBase):
    pass


class BrigadeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    specialization: str | None = None
    shift_start: time | None = None
    shift_end: time | None = None
    garage_latitude: float | None = None
    garage_longitude: float | None = None


class BrigadeMemberBase(BaseModel):
    full_name: str
    role: str


class BrigadeMemberCreate(BrigadeMemberBase):
    brigade_id: int


class BrigadeMemberResponse(BrigadeMemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brigade_id: int


class BrigadeResponse(BrigadeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    members: list[BrigadeMemberResponse] = []
    vehicles: list["VehicleShort"] = []
    garage_address: str | None = None


class BrigadeShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    specialization: str


# Resolve forward references
from schemas.vehicle import VehicleShort
BrigadeResponse.model_rebuild()
