from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Pet, User
from app.repositories import pet_repository

router = APIRouter(prefix="/pets", tags=["Pets"])


class PetCreate(BaseModel):
    name: str
    species: str


@router.get("")
def list_pets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "species": p.species} for p in pet_repository.by_owner(db, user.id)]


@router.post("", status_code=201)
def create_pet(data: PetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(pet_repository.by_owner(db, user.id)) >= 5:
        raise HTTPException(status_code=400, detail="Máximo 5 mascotas por dueño")
    if data.species not in ("perro", "gato"):
        raise HTTPException(status_code=400, detail="Solo atendemos perros y gatos")
    pet = Pet(name=data.name, species=data.species, owner_id=user.id)
    db.add(pet)
    db.commit()
    return {"id": pet.id}


@router.get("/{pet_id}")
def get_pet(pet_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(status_code=404)
    return {"pet": pet, "owner": pet.owner}
