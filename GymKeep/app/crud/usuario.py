from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import hashear_clave
from app.models.auth import ROL_ADMIN, Usuario

INTENTOS_MAX = 5
BLOQUEO_MIN = 15


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(momento: Optional[datetime]) -> Optional[datetime]:
    """SQLite devuelve fechas sin zona horaria (en UTC); Postgres, con zona."""
    if momento is None:
        return None
    return momento.replace(tzinfo=timezone.utc) if momento.tzinfo is None else momento


def contar(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Usuario)) or 0


def contar_admins_activos(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Usuario).where(Usuario.rol == ROL_ADMIN, Usuario.activo.is_(True))) or 0


def get(db: Session, usuario_id: int) -> Optional[Usuario]:
    return db.get(Usuario, usuario_id)


def get_por_run(db: Session, run: str) -> Optional[Usuario]:
    return db.scalar(select(Usuario).where(Usuario.run == run))


def listar(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.nombre)))


def crear(db: Session, run: str, nombre: str, rol: str, clave: str) -> Usuario:
    usuario = Usuario(run=run, nombre=nombre.strip(), rol=rol, clave_hash=hashear_clave(clave), activo=True)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def cambiar_clave(db: Session, usuario: Usuario, clave: str) -> None:
    usuario.clave_hash = hashear_clave(clave)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.sesion_version = (usuario.sesion_version or 0) + 1  # cierra las otras sesiones
    db.commit()


def segundos_bloqueo(usuario: Usuario) -> int:
    hasta = _utc(usuario.bloqueado_hasta)
    if hasta is None:
        return 0
    return max(0, int((hasta - ahora()).total_seconds()) + 1) if hasta > ahora() else 0


def registrar_fallo(db: Session, usuario: Usuario) -> None:
    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
    if usuario.intentos_fallidos >= INTENTOS_MAX:
        usuario.bloqueado_hasta = ahora() + timedelta(minutes=BLOQUEO_MIN)
        usuario.intentos_fallidos = 0
    db.commit()


def registrar_acceso(db: Session, usuario: Usuario) -> None:
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora()
    db.commit()
