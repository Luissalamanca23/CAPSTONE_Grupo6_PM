from fastapi import APIRouter, Depends

from app.api.v1 import (
    auth,
    camaras,
    empresas,
    equipamiento,
    estadisticas,
    eventos_ia,
    incidencias,
    informes,
    mantenimientos,
    modelos_ia,
    sesiones_uso,
    sucursales,
    vision,
    zonas,
)
from app.core.seguridad import requerir_sesion

# Toda la API exige sesion salvo las rutas publicas de core/seguridad.py (formulario del QR y login).
api_router = APIRouter(dependencies=[Depends(requerir_sesion)])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(empresas.router, prefix="/empresas", tags=["Empresas"])
api_router.include_router(sucursales.router, prefix="/sucursales", tags=["Sucursales"])
api_router.include_router(zonas.router, prefix="/zonas", tags=["Zonas"])
api_router.include_router(equipamiento.router, prefix="/equipamiento", tags=["Equipamiento"])
api_router.include_router(incidencias.router, prefix="/incidencias", tags=["Incidencias"])
api_router.include_router(mantenimientos.router, prefix="/mantenimientos", tags=["Mantenimientos"])
api_router.include_router(camaras.router, prefix="/camaras", tags=["Camaras"])
api_router.include_router(modelos_ia.router, prefix="/modelos-ia", tags=["Modelos IA"])
api_router.include_router(eventos_ia.router, prefix="/eventos-ia", tags=["Eventos IA"])
api_router.include_router(sesiones_uso.router, prefix="/sesiones-uso", tags=["Sesiones de uso"])
api_router.include_router(vision.router, prefix="/vision", tags=["Vision (integracion)"])
api_router.include_router(estadisticas.router, prefix="/estadisticas", tags=["Estadisticas"])
api_router.include_router(informes.router, prefix="/informes", tags=["Informes"])
