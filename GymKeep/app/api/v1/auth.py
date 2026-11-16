"""Inicio y cierre de sesion, y administracion de usuarios (solo administradores)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core import auth
from app.core.database import get_db
from app.core.limitador import LimitadorVentana
from app.core.seguridad import CABECERA_SESION, requerir_admin, requerir_usuario
from app.crud import usuario as crud_usuario
from app.models.auth import ROL_ADMIN, Usuario
from app.schemas.auth import CambiarClaveIn, EstadoAuthOut, LoginIn, UsuarioCreate, UsuarioOut, UsuarioUpdate

router = APIRouter()

# Tope de intentos de login por direccion IP (ademas del bloqueo por cuenta).
limitador_login_ip = LimitadorVentana(maximo=30, ventana=600)

ERROR_CREDENCIALES = "RUN o clave incorrectos."


def _ip(request: Request) -> str:
    # Detras del proxy (nginx) la IP real viene en X-Forwarded-For.
    reenviada = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if reenviada:
        return reenviada
    return request.client.host if request.client else "desconocida"


def _es_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"


def _poner_cookie(response: Response, request: Request, token: str, vigencia: int) -> None:
    response.set_cookie(
        auth.COOKIE_SESION,
        token,
        max_age=vigencia,
        httponly=True,
        samesite="lax",
        secure=_es_https(request),
        path="/",
    )


def _quitar_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(auth.COOKIE_SESION, path="/", httponly=True, samesite="lax", secure=_es_https(request))


@router.get("/estado", response_model=EstadoAuthOut)
def estado(db: Session = Depends(get_db)):
    """Publico: la pantalla de login lo usa para avisar si todavia no hay ninguna cuenta."""
    return EstadoAuthOut(hay_usuarios=crud_usuario.contar(db) > 0)


@router.post("/login", response_model=UsuarioOut)
def login(datos: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if not limitador_login_ip.permitir(_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Espera unos minutos e intenta de nuevo.")

    run = auth.normalizar_run(datos.run)
    usuario = crud_usuario.get_por_run(db, run) if run else None

    if usuario is None or not usuario.activo:
        # Mismo trabajo que con una cuenta real, para no delatar si el RUN existe por el tiempo.
        auth.verificar_clave(datos.clave, auth.HASH_FALSO)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ERROR_CREDENCIALES, headers=CABECERA_SESION)

    espera = crud_usuario.segundos_bloqueo(usuario)
    if espera:
        minutos = max(1, -(-espera // 60))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Cuenta bloqueada por demasiados intentos. Intenta de nuevo en {minutos} min.",
        )

    if not auth.verificar_clave(datos.clave, usuario.clave_hash):
        crud_usuario.registrar_fallo(db, usuario)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, ERROR_CREDENCIALES, headers=CABECERA_SESION)

    crud_usuario.registrar_acceso(db, usuario)
    token, vigencia = auth.crear_token(db, usuario.id, usuario.sesion_version)
    _poner_cookie(response, request, token, vigencia)
    return usuario


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request):
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    _quitar_cookie(respuesta, request)
    return respuesta


@router.get("/me", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(requerir_usuario)):
    return usuario


@router.post("/cambiar-clave", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_clave(
    datos: CambiarClaveIn,
    request: Request,
    usuario: Usuario = Depends(requerir_usuario),
    db: Session = Depends(get_db),
):
    if not limitador_login_ip.permitir(_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Espera unos minutos e intenta de nuevo.")
    if not auth.verificar_clave(datos.clave_actual, usuario.clave_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La clave actual no es correcta.")
    crud_usuario.cambiar_clave(db, usuario, datos.clave_nueva)
    # Cambiar la clave cierra las demas sesiones; esta se renueva para no sacar a quien la cambia.
    token, vigencia = auth.crear_token(db, usuario.id, usuario.sesion_version)
    respuesta = Response(status_code=status.HTTP_204_NO_CONTENT)
    _poner_cookie(respuesta, request, token, vigencia)
    return respuesta


# ----------------------------------------------------------------------------- usuarios (admin)


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(_: Usuario = Depends(requerir_admin), db: Session = Depends(get_db)):
    return crud_usuario.listar(db)


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCreate, _: Usuario = Depends(requerir_admin), db: Session = Depends(get_db)):
    if crud_usuario.get_por_run(db, datos.run):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese RUN.")
    return crud_usuario.crear(db, datos.run, datos.nombre, datos.rol, datos.clave)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    actual: Usuario = Depends(requerir_admin),
    db: Session = Depends(get_db),
):
    objetivo = crud_usuario.get(db, usuario_id)
    if objetivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La cuenta no existe.")

    deja_de_ser_admin = (datos.rol is not None and datos.rol != ROL_ADMIN) or datos.activo is False
    if deja_de_ser_admin and objetivo.es_admin and objetivo.activo:
        if objetivo.id == actual.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes quitarte el acceso de administrador a ti mismo.")
        if crud_usuario.contar_admins_activos(db) <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Debe quedar al menos un administrador activo.")
    if datos.activo is False and objetivo.id == actual.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivar tu propia cuenta.")

    if datos.clave is not None and objetivo.id == actual.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Para cambiar tu propia clave usa la opcion Cambiar mi clave.")

    cierra_sesiones = False
    if datos.nombre is not None:
        objetivo.nombre = datos.nombre.strip()
    if datos.rol is not None and datos.rol != objetivo.rol:
        objetivo.rol = datos.rol
        cierra_sesiones = True
    if datos.activo is not None and datos.activo != objetivo.activo:
        objetivo.activo = datos.activo
        cierra_sesiones = True
        if datos.activo:  # al reactivar, parte sin bloqueos
            objetivo.intentos_fallidos = 0
            objetivo.bloqueado_hasta = None
    if cierra_sesiones:
        objetivo.sesion_version = (objetivo.sesion_version or 0) + 1
    db.commit()

    if datos.clave is not None:
        crud_usuario.cambiar_clave(db, objetivo, datos.clave)
    db.refresh(objetivo)
    return objetivo
