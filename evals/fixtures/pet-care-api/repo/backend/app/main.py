from fastapi import FastAPI

from app.routers import appointments, auth, pets, services

app = FastAPI(title="pet-care-api")

app.include_router(auth.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(pets.router, prefix="/api")
app.include_router(services.router, prefix="/api")
