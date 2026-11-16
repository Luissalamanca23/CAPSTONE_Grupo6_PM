import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.gymkeep import EstadoEquipo, EstadoIncidencia, Equipo, Mantenimiento, QrEquipo
from app.schemas.equipamiento import EquipoCreate, EquipoUpdate, TcoEquipoOut

# selectinload (no joinedload) para incidencias: es una relacion 1:N y evita duplicar filas
# de equipo al traer el join; se usa solo para contar abiertas (equipo.incidencias_abiertas).
CARGA_RELACIONES = (
    joinedload(Equipo.sucursal),
    joinedload(Equipo.zona),
    joinedload(Equipo.qr),
    selectinload(Equipo.incidencias),
)


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


def get_equipo_by_serie(db: Session, numero_serie: str) -> Optional[Equipo]:
    return db.query(Equipo).filter(Equipo.numero_serie == numero_serie).first()


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
    datos = equipo_in.model_dump(exclude_unset=True)
    # Columnas NOT NULL: un null explicito (campo borrado en un formulario) se ignora.
    for campo in ("codigo_activo", "nombre", "estado"):
        if datos.get(campo) is None:
            datos.pop(campo, None)
    nuevo_estado = datos.get("estado")

    for campo, valor in datos.items():
        setattr(equipo, campo, valor)

    # Sincronizacion: al mandar el equipo a mantenimiento, las incidencias que seguian
    # "pendientes" (nadie las habia tomado todavia) pasan a "en_proceso" -- ya hay alguien
    # trabajando en la maquina. Las que ya estaban en_proceso/resueltas/descartadas no se
    # tocan. El regreso a "operativo" queda a criterio del tecnico (no se automatiza).
    if nuevo_estado == EstadoEquipo.en_mantenimiento:
        for incidencia in equipo.incidencias:
            if incidencia.estado == EstadoIncidencia.pendiente:
                incidencia.estado = EstadoIncidencia.en_proceso

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


def _a_float(valor) -> float:
    return round(float(valor or 0), 2)


def calcular_tco(db: Session, equipos: list[Equipo]) -> list[TcoEquipoOut]:
    """Costo total de propiedad de cada equipo (RF-32): precio de compra + costo de todas sus
    mantenciones (cada una registra su costo total, que ya incluye repuestos y mano de obra).
    Un equipo sin mantenciones ni precio de compra da TCO 0; sin precio de compra solo suma
    mantenciones (`adquisicion_registrada` lo indica)."""
    if not equipos:
        return []
    ids = [e.id for e in equipos]
    filas = (
        db.query(
            Mantenimiento.equipo_id,
            Mantenimiento.tipo,
            func.coalesce(func.sum(Mantenimiento.costo_total), 0),
            func.count(Mantenimiento.id),
        )
        .filter(Mantenimiento.equipo_id.in_(ids))
        .group_by(Mantenimiento.equipo_id, Mantenimiento.tipo)
        .all()
    )
    por_equipo: dict[int, dict] = {}
    for equipo_id, tipo, suma, cantidad in filas:
        acumulado = por_equipo.setdefault(equipo_id, {"correctivo": 0.0, "preventivo": 0.0, "otros": 0.0, "cantidad": 0})
        clave = tipo if tipo in ("correctivo", "preventivo") else "otros"
        acumulado[clave] += float(suma or 0)
        acumulado["cantidad"] += int(cantidad or 0)

    resultado = []
    for equipo in equipos:
        datos = por_equipo.get(equipo.id, {"correctivo": 0.0, "preventivo": 0.0, "otros": 0.0, "cantidad": 0})
        mantenciones = datos["correctivo"] + datos["preventivo"] + datos["otros"]
        adquisicion = None if equipo.costo_adquisicion is None else _a_float(equipo.costo_adquisicion)
        resultado.append(
            TcoEquipoOut(
                equipo_id=equipo.id,
                codigo_activo=equipo.codigo_activo,
                nombre=equipo.nombre,
                categoria=equipo.categoria,
                costo_adquisicion=adquisicion,
                adquisicion_registrada=adquisicion is not None,
                costo_mantenciones=_a_float(mantenciones),
                costo_correctivo=_a_float(datos["correctivo"]),
                costo_preventivo=_a_float(datos["preventivo"]),
                cantidad_mantenciones=datos["cantidad"],
                tco=_a_float((adquisicion or 0) + mantenciones),
            )
        )
    return resultado

