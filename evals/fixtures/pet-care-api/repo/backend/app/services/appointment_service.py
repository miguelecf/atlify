from sqlalchemy.orm import Session

from app.models import Appointment, User
from app.repositories import appointment_repository, pet_repository
from app.schemas.appointment import AppointmentCreate, AppointmentOut


class SlotTaken(Exception):
    pass


def _to_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(id=a.id, pet_name=a.pet.name, service_name=a.service.name,
                          starts_at=a.starts_at, status=a.status)


def list_for_owner(db: Session, user: User) -> list[AppointmentOut]:
    result = []
    for pet in pet_repository.by_owner(db, user.id):
        for a in appointment_repository.by_pet(db, pet.id):
            result.append(_to_out(a))
    return result


def book(db: Session, user: User, data: AppointmentCreate) -> AppointmentOut:
    pet = pet_repository.get(db, data.pet_id)
    if pet is None or pet.owner_id != user.id:
        raise PermissionError("La mascota no es del usuario")
    if appointment_repository.exists_at(db, data.service_id, data.starts_at):
        raise SlotTaken()
    a = appointment_repository.add(db, Appointment(**data.model_dump()))
    db.commit()
    return _to_out(a)


def cancel(db: Session, appointment_id: int) -> None:
    a = appointment_repository.get(db, appointment_id)
    if a is not None:
        a.status = "cancelled"
        db.commit()
