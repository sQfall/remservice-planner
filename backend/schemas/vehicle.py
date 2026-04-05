from pydantic import BaseModel, ConfigDict


class VehicleBase(BaseModel):
    brigade_id: int
    plate: str
    vehicle_type: str
    year: int


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plate: str | None = None
    vehicle_type: str | None = None
    year: int | None = None


class VehicleShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    vehicle_type: str
    year: int


class VehicleResponse(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
