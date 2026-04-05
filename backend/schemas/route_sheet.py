from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from schemas.planning import RoutePointResponse, RouteSegmentResponse
from schemas.brigade import BrigadeResponse


class RouteSheetPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    address: str
    work_type: str
    arrival_time: datetime | None = None
    departure_time: datetime | None = None
    contact_person: str | None = None
    phone: str | None = None
    description: str | None = None


class RouteSheetSegment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_address: str | None = None
    to_address: str | None = None
    duration: int
    distance: float
    is_garage_segment: bool


class RouteSheetEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brigade: BrigadeResponse
    points: list[RouteSheetPoint]
    segments: list[RouteSheetSegment]
    total_duration: int
    total_distance: float


class RouteSheetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_date: datetime
    entries: list[RouteSheetEntry]
