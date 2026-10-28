from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas.appointment import AppointmentCreate, AppointmentOut
from app.services import appointment_service

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("", response_model=list[AppointmentOut])
def list_appointments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return appointment_service.list_for_owner(db, user)


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(data: AppointmentCreate, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    try:
        return appointment_service.book(db, user, data)
    except appointment_service.SlotTaken:
        raise HTTPException(status_code=409, detail="Ese horario ya está ocupado")


@router.delete("/{appointment_id}", status_code=204)
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment_service.cancel(db, appointment_id)
