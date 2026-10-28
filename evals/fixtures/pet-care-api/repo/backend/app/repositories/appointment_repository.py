from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment


def by_pet(db: Session, pet_id: int) -> list[Appointment]:
    return list(db.scalars(select(Appointment).where(Appointment.pet_id == pet_id)))


def exists_at(db: Session, service_id: int, starts_at: datetime) -> bool:
    q = select(Appointment.id).where(Appointment.service_id == service_id,
                                     Appointment.starts_at == starts_at,
                                     Appointment.status == "scheduled")
    return db.scalar(q) is not None


def get(db: Session, appointment_id: int) -> Appointment | None:
    return db.get(Appointment, appointment_id)


def add(db: Session, a: Appointment) -> Appointment:
    db.add(a)
    db.flush()
    return a
