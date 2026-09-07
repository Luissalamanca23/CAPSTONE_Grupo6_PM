from fastapi import APIRouter

from app.api.v1 import equipamiento, incidencias

api_router = APIRouter()
api_router.include_router(equipamiento.router, prefix="/equipamiento", tags=["Equipamiento"])
api_router.include_router(incidencias.router, prefix="/incidencias", tags=["Incidencias"])
