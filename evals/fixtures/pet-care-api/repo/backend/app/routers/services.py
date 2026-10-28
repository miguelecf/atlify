from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Service

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("")
def list_services(db: Session = Depends(get_db)):
    return db.scalars(select(Service)).all()
