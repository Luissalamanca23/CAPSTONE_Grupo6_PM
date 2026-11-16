"""Control de acceso de toda la API.

`requerir_sesion` se aplica a TODO /api/v1 (ver api/v1/router.py): lo que no esta en la lista
de rutas publicas exige sesion. Asi un endpoint nuevo queda protegido por defecto.

Quien puede pasar:
- Una persona con sesion iniciada (cookie HttpOnly). Los tecnicos no pueden borrar datos
  (DELETE): solo los administradores.
- El pipeline de vision, con la cabecera X-Pipeline-Key (si VISION_PIPELINE_KEY esta definida).
  Es una credencial de servicio: no borra datos ni administra usuarios.

Las peticiones que modifican datos con cookie tambien comprueban el origen (Origin) para que
otro sitio web no pueda usar la sesion abierta del navegador.
"""

import hmac
import re
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import auth
from app.core.config import settings
from app.core.database import get_db
from app.core.origenes import origen_confiable
from app.models.auth import Usuario

# Cabecera que le avisa al panel que la sesion no existe o vencio (distinto de un 401 por PIN).
CABECERA_SESION = {"WWW-Authenticate": "GymKeep-Sesion"}

# (metodo, regex de la ruta SIN el prefijo /api/v1). Es todo lo que puede usar quien no inicio sesion.
RUTAS_PUBLICAS = [
    # Formulario publico del QR de cada maquina.
    ("GET", re.compile(r"^/equipamiento/qr/[^/]+$")),
    ("GET", re.compile(r"^/incidencias/tipos-falla$")),
    ("POST", re.compile(r"^/incidencias/reporte-qr$")),
    # Inicio y cierre de sesion.
    ("POST", re.compile(r"^/auth/login$")),
    ("POST", re.compile(r"^/auth/logout$")),
    ("GET", re.compile(r"^/auth/estado$")),
]
# Quitar la zona de una maquina en una camara es un DELETE que si puede hacer un tecnico.
DELETE_PERMITIDO_A_TECNICOS = [re.compile(r"^/vision/camaras/\d+/maquinas/\d+$")]
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def _ruta(request: Request) -> str:
    ruta = request.url.path
    if ruta.startswith(settings.api_v1_prefix):
        ruta = ruta[len(settings.api_v1_prefix):]
    return ruta.rstrip("/") or "/"


def es_ruta_publica(metodo: str, ruta: str) -> bool:
    return any(m == metodo and patron.match(ruta) for m, patron in RUTAS_PUBLICAS)


def usuario_de_sesion(request: Request, db: Session) -> Optional[Usuario]:
    """Usuario de la cookie de sesion, o None si falta, esta alterada, vencio o fue revocada."""
    datos = auth.leer_token(db, request.cookies.get(auth.COOKIE_SESION))
    if not datos:
        return None
    usuario = db.get(Usuario, datos["sub"])
    if usuario is None or not usuario.activo or usuario.sesion_version != datos.get("sv"):
        return None
    return usuario


def _clave_pipeline_valida(request: Request) -> bool:
    enviada = request.headers.get("x-pipeline-key")
    if not settings.vision_pipeline_key or enviada is None:
        return False
    return hmac.compare_digest(enviada.encode(), settings.vision_pipeline_key.encode())


def _sin_sesion() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesion para continuar.", headers=CABECERA_SESION)


def requerir_sesion(request: Request, db: Session = Depends(get_db)) -> None:
    """Dependencia global de la API. Deja en `request.state.usuario` a la persona con sesion."""
    request.state.usuario = None
    request.state.es_pipeline = False
    metodo, ruta = request.method, _ruta(request)
    if metodo == "OPTIONS" or es_ruta_publica(metodo, ruta):
        # En las rutas publicas igual se reconoce la sesion, por si cambia lo que se devuelve.
        request.state.usuario = usuario_de_sesion(request, db) if metodo != "OPTIONS" else None
        return

    usuario = usuario_de_sesion(request, db)
    if usuario is not None:
        if metodo not in METODOS_SEGUROS:
            origen = request.headers.get("origin")
            if origen and not origen_confiable(origen, request.headers.get("host"), request.headers.get("x-forwarded-host")):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido.")
        if metodo == "DELETE" and not usuario.es_admin and not any(p.match(ruta) for p in DELETE_PERMITIDO_A_TECNICOS):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo un administrador puede eliminar datos.")
        request.state.usuario = usuario
        return

    if _clave_pipeline_valida(request):
        if metodo == "DELETE" or ruta.startswith("/auth"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta credencial no permite esa accion.")
        request.state.es_pipeline = True
        return

    raise _sin_sesion()


def requerir_usuario(request: Request) -> Usuario:
    """Para los endpoints que son solo de personas (no del pipeline)."""
    usuario = getattr(request.state, "usuario", None)
    if usuario is None:
        raise _sin_sesion()
    return usuario


def requerir_admin(usuario: Usuario = Depends(requerir_usuario)) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo un administrador puede hacer esto.")
    return usuario
