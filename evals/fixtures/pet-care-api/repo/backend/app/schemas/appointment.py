from datetime import datetime

from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    pet_id: int
    service_id: int
    starts_at: datetime


class AppointmentOut(BaseModel):
    id: int
    pet_name: str
    service_name: str
    starts_at: datetime
    status: str
