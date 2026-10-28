from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Pet


def by_owner(db: Session, owner_id: int) -> list[Pet]:
    return list(db.scalars(select(Pet).where(Pet.owner_id == owner_id)))


def get(db: Session, pet_id: int) -> Pet | None:
    return db.get(Pet, pet_id)
