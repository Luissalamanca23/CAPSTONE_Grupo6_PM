from fastapi import APIRouter

from app.api.v1 import (
    camaras,
    empresas,
    equipamiento,
    eventos_ia,
    incidencias,
    modelos_ia,
    sesiones_uso,
    sucursales,
    zonas,
)

api_router = APIRouter()
api_router.include_router(empresas.router, prefix="/empresas", tags=["Empresas"])
api_router.include_router(sucursales.router, prefix="/sucursales", tags=["Sucursales"])
api_router.include_router(zonas.router, prefix="/zonas", tags=["Zonas"])
api_router.include_router(equipamiento.router, prefix="/equipamiento", tags=["Equipamiento"])
api_router.include_router(incidencias.router, prefix="/incidencias", tags=["Incidencias"])
api_router.include_router(camaras.router, prefix="/camaras", tags=["Camaras"])
api_router.include_router(modelos_ia.router, prefix="/modelos-ia", tags=["Modelos IA"])
api_router.include_router(eventos_ia.router, prefix="/eventos-ia", tags=["Eventos IA"])
api_router.include_router(sesiones_uso.router, prefix="/sesiones-uso", tags=["Sesiones de uso"])
