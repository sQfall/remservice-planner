from __future__ import annotations
from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field
from schemas.brigade import BrigadeShort


class ServiceRequestBase(BaseModel):
    address: str
    latitude: float
    longitude: float
    work_type: str
    description: str | None = None
    priority: str = "medium"
    contact_person: str | None = None
    phone: str | None = None
    estimated_duration: int | None = None
    time_window_start: time | None = None
    time_window_end: time | None = None


class ServiceRequestCreate(ServiceRequestBase):
    address: str = Field(min_length=1)
    contact_person: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    planned_at: datetime


class ServiceRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    work_type: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    estimated_duration: int | None = None
    planned_at: datetime | None = None
    time_window_start: time | None = None
    time_window_end: time | None = None


class ServiceRequestResponse(ServiceRequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    planned_at: datetime | None = None
    brigade: BrigadeShort | None = None
