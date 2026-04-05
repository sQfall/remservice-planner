from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from schemas.request import ServiceRequestResponse


class RoutePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brigade_id: int
    sequence: int
    arrival_time: datetime | None = None
    departure_time: datetime | None = None
    request: ServiceRequestResponse


class RouteSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_point_id: int | None = None
    to_point_id: int | None = None
    duration: int
    distance: float
    geometry_json: str | None = None
    is_garage_segment: bool
    garage_segment_type: str | None = None


class DailyPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_date: datetime
    status: str
    created_by: str | None = None
    created_at: datetime
    route_points: list[RoutePointResponse] = []


class PlanningRequest(BaseModel):
    plan_date: datetime
    use_or_tools: bool = False
