import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.gymkeep import Equipo, QrEquipo
from app.schemas.equipamiento import EquipoCreate, EquipoUpdate

CARGA_RELACIONES = (joinedload(Equipo.sucursal), joinedload(Equipo.zona), joinedload(Equipo.qr))


def get_equipo(db: Session, equipo_id: int) -> Optional[Equipo]:
    return db.query(Equipo).options(*CARGA_RELACIONES).filter(Equipo.id == equipo_id).first()


def get_equipo_by_token(db: Session, token: str) -> Optional[Equipo]:
    """Resuelve un equipo a partir del token UUID de un QR activo (y no expirado)."""
    try:
        token_uuid = uuid.UUID(str(token))
    except (ValueError, AttributeError, TypeError):
        return None

    ahora = datetime.now(timezone.utc)
    qr = (
        db.query(QrEquipo)
        .filter(QrEquipo.token == token_uuid, QrEquipo.activo.is_(True))
        .first()
    )
    if not qr:
        return None
    if qr.fecha_expiracion is not None and qr.fecha_expiracion <= ahora:
        return None
    return get_equipo(db, qr.equipo_id)


def list_equipos(db: Session, skip: int = 0, limit: int = 100, sucursal_id: Optional[int] = None):
    query = db.query(Equipo).options(*CARGA_RELACIONES)
    if sucursal_id is not None:
        query = query.filter(Equipo.sucursal_id == sucursal_id)
    return query.order_by(Equipo.id).offset(skip).limit(limit).all()


def get_equipo_by_codigo_activo(db: Session, sucursal_id: int, codigo_activo: str) -> Optional[Equipo]:
    return (
        db.query(Equipo)
        .filter(Equipo.sucursal_id == sucursal_id, Equipo.codigo_activo == codigo_activo)
        .first()
    )


def create_equipo(db: Session, equipo_in: EquipoCreate) -> Equipo:
    """Registra el equipo y le emite automaticamente su primer QR activo (UUID seguro)."""
    equipo = Equipo(**equipo_in.model_dump())
    db.add(equipo)
    db.flush()  # asigna equipo.id sin cerrar la transaccion

    qr = QrEquipo(equipo_id=equipo.id, token=uuid.uuid4(), activo=True)
    db.add(qr)

    db.commit()
    db.refresh(equipo)
    return equipo


def update_equipo(db: Session, equipo: Equipo, equipo_in: EquipoUpdate) -> Equipo:
    for campo, valor in equipo_in.model_dump(exclude_unset=True).items():
        setattr(equipo, campo, valor)
    db.commit()
    db.refresh(equipo)
    return equipo


def regenerar_qr(db: Session, equipo: Equipo, motivo: Optional[str] = None) -> QrEquipo:
    """Revoca el QR activo (si existe) y emite uno nuevo, preservando el historial."""
    ahora = datetime.now(timezone.utc)
    activo_actual = equipo.qr_activo
    if activo_actual:
        activo_actual.activo = False
        activo_actual.fecha_revocacion = ahora
        activo_actual.motivo_revocacion = motivo or "Reemision manual desde el panel."

    nuevo = QrEquipo(equipo_id=equipo.id, token=uuid.uuid4(), activo=True)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def tiene_incidencias(db: Session, equipo: Equipo) -> bool:
    """El esquema define equipos.incidencias con ON DELETE RESTRICT (se conserva el
    historial de fallas por auditoria): no se puede borrar un equipo que ya tiene reportes."""
    from app.models.gymkeep import Incidencia

    return db.query(Incidencia.id).filter(Incidencia.equipo_id == equipo.id).first() is not None


def delete_equipo(db: Session, equipo: Equipo) -> None:
    db.delete(equipo)
    db.commit()
