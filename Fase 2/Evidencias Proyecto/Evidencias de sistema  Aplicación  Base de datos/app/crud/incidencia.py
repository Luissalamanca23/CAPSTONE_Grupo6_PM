from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.incidencia import (
    DESCRIPCION_TIPO_FALLA,
    NIVEL_POR_TIPO_FALLA,
    EstadoIncidencia,
    Incidencia,
    PrioridadIncidencia,
)
from app.schemas.incidencia import IncidenciaCreate, IncidenciaUpdate


def get_incidencia(db: Session, incidencia_id: int) -> Optional[Incidencia]:
    return db.query(Incidencia).filter(Incidencia.id == incidencia_id).first()


def list_incidencias(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    estado: Optional[EstadoIncidencia] = None,
    equipo_id: Optional[int] = None,
):
    query = db.query(Incidencia)
    if estado is not None:
        query = query.filter(Incidencia.estado == estado)
    if equipo_id is not None:
        query = query.filter(Incidencia.equipo_id == equipo_id)
    return query.order_by(Incidencia.fecha_reporte.desc()).offset(skip).limit(limit).all()


def create_incidencia(db: Session, incidencia_in: IncidenciaCreate) -> Incidencia:
    datos = incidencia_in.model_dump()

    # El formulario publico no pide texto libre: se autocompleta una descripcion legible
    # a partir del tipo de falla elegido.
    if not datos.get("descripcion"):
        datos["descripcion"] = DESCRIPCION_TIPO_FALLA.get(
            incidencia_in.tipo_falla, "Falla reportada."
        )

    # La prioridad se clasifica sola segun el tipo de falla, salvo que un tecnico la
    # haya definido manualmente al crear la incidencia desde el panel.
    if not datos.get("prioridad"):
        datos["prioridad"] = NIVEL_POR_TIPO_FALLA.get(
            incidencia_in.tipo_falla, PrioridadIncidencia.media
        )

    incidencia = Incidencia(**datos)
    db.add(incidencia)
    db.commit()
    db.refresh(incidencia)
    return incidencia


def update_incidencia(db: Session, incidencia: Incidencia, incidencia_in: IncidenciaUpdate) -> Incidencia:
    datos = incidencia_in.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        setattr(incidencia, campo, valor)
    if datos.get("estado") == EstadoIncidencia.resuelta and incidencia.fecha_resolucion is None:
        incidencia.fecha_resolucion = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incidencia)
    return incidencia
