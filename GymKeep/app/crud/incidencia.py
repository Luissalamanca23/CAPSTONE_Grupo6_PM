from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.gymkeep import Equipo, EstadoIncidencia, Incidencia, OrigenIncidencia, TipoFalla
from app.schemas.incidencia import IncidenciaCreate, IncidenciaUpdate

CARGA_RELACIONES = (joinedload(Incidencia.tipo_falla),)


def get_incidencia(db: Session, incidencia_id: int) -> Optional[Incidencia]:
    return db.query(Incidencia).options(*CARGA_RELACIONES).filter(Incidencia.id == incidencia_id).first()


def list_incidencias(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    estado: Optional[EstadoIncidencia] = None,
    equipo_id: Optional[int] = None,
):
    query = db.query(Incidencia).options(*CARGA_RELACIONES)
    if estado is not None:
        query = query.filter(Incidencia.estado == estado)
    if equipo_id is not None:
        query = query.filter(Incidencia.equipo_id == equipo_id)
    return query.order_by(Incidencia.fecha_reporte.desc()).offset(skip).limit(limit).all()


def _crear_incidencia(
    db: Session,
    *,
    equipo_id: int,
    tipo_falla: TipoFalla,
    origen: OrigenIncidencia,
    reportado_por: Optional[str] = None,
    descripcion: Optional[str] = None,
    prioridad=None,
    qr_id: Optional[int] = None,
) -> Incidencia:
    incidencia = Incidencia(
        equipo_id=equipo_id,
        tipo_falla=tipo_falla,
        qr_id=qr_id,
        origen=origen,
        # El formulario publico no pide texto libre: se autocompleta una descripcion legible
        # a partir del tipo de falla elegido (catalogo `tipos_falla`).
        descripcion=descripcion or tipo_falla.descripcion,
        reportado_por=reportado_por,
        # La prioridad se clasifica sola segun la prioridad_base del tipo de falla, salvo que
        # un tecnico la haya definido manualmente al crear la incidencia desde el panel.
        prioridad=prioridad or tipo_falla.prioridad_base,
    )
    db.add(incidencia)
    db.commit()
    db.refresh(incidencia)
    return incidencia


def create_incidencia(db: Session, incidencia_in: IncidenciaCreate, tipo_falla: TipoFalla) -> Incidencia:
    """Creacion manual desde el panel de tecnicos."""
    return _crear_incidencia(
        db,
        equipo_id=incidencia_in.equipo_id,
        tipo_falla=tipo_falla,
        origen=incidencia_in.origen,
        reportado_por=incidencia_in.reportado_por,
        descripcion=incidencia_in.descripcion,
        prioridad=incidencia_in.prioridad,
    )


def create_incidencia_por_qr(
    db: Session, equipo: Equipo, tipo_falla: TipoFalla, reportado_por: str
) -> Incidencia:
    """Portal de Reporte Express: fecha/hora y origen='qr' quedan registrados automaticamente."""
    qr_activo = equipo.qr_activo
    return _crear_incidencia(
        db,
        equipo_id=equipo.id,
        tipo_falla=tipo_falla,
        origen=OrigenIncidencia.qr,
        reportado_por=reportado_por,
        qr_id=qr_activo.id if qr_activo else None,
    )


def update_incidencia(db: Session, incidencia: Incidencia, incidencia_in: IncidenciaUpdate) -> Incidencia:
    datos = incidencia_in.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        setattr(incidencia, campo, valor)
    if datos.get("estado") == EstadoIncidencia.resuelta and incidencia.fecha_resolucion is None:
        incidencia.fecha_resolucion = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incidencia)
    return incidencia
