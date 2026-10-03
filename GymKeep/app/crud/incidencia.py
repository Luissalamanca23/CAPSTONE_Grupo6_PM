from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.gymkeep import (
    Equipo,
    EstadoEquipo,
    EstadoIncidencia,
    Incidencia,
    OrigenIncidencia,
    PrioridadIncidencia,
    TipoFalla,
)
from app.schemas.incidencia import IncidenciaCreate, IncidenciaUpdate

# equipo -> selectinload(incidencias): necesario para que equipo.incidencias_abiertas (ver
# gymkeep.py) salga calculado en el listado de incidencias, no solo en el de equipos.
CARGA_RELACIONES = (
    joinedload(Incidencia.tipo_falla),
    joinedload(Incidencia.equipo).selectinload(Equipo.incidencias),
)


def get_incidencia(db: Session, incidencia_id: int) -> Optional[Incidencia]:
    return db.query(Incidencia).options(*CARGA_RELACIONES).filter(Incidencia.id == incidencia_id).first()


def _query_incidencias_filtrada(
    db: Session,
    *,
    estado: Optional[EstadoIncidencia] = None,
    equipo_id: Optional[int] = None,
    categoria: Optional[str] = None,
    prioridad: Optional[PrioridadIncidencia] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    q: Optional[str] = None,
):
    """Arma el query base con todos los filtros del historial de incidencias (panel de
    tecnicos): estado, equipo, categoria del tipo de falla, prioridad, rango de fechas y
    texto libre. Se comparte entre `list_incidencias` (trae la pagina) y
    `count_incidencias` (total real, ignorando skip/limit) para que la paginacion del
    frontend sepa cuantas paginas hay sin traer todos los registros de una vez."""
    query = db.query(Incidencia)

    # Los joins solo se agregan si algun filtro realmente los necesita, para no duplicar
    # el join a la misma tabla si mas de un filtro la usa.
    necesita_tipo_falla = categoria is not None or bool(q)
    necesita_equipo = bool(q)

    if necesita_tipo_falla:
        query = query.join(TipoFalla, Incidencia.tipo_falla_id == TipoFalla.id)
    if necesita_equipo:
        query = query.join(Equipo, Incidencia.equipo_id == Equipo.id)

    if estado is not None:
        query = query.filter(Incidencia.estado == estado)
    if equipo_id is not None:
        query = query.filter(Incidencia.equipo_id == equipo_id)
    if prioridad is not None:
        query = query.filter(Incidencia.prioridad == prioridad)
    if categoria is not None:
        query = query.filter(TipoFalla.categoria == categoria)
    if fecha_desde is not None:
        query = query.filter(Incidencia.fecha_reporte >= fecha_desde)
    if fecha_hasta is not None:
        # fecha_hasta es un DIA (no timestamp): se incluye completo (hasta antes de la
        # medianoche siguiente), para no perder incidencias reportadas ese mismo dia.
        query = query.filter(Incidencia.fecha_reporte < fecha_hasta + timedelta(days=1))
    if q:
        patron = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Incidencia.descripcion.ilike(patron),
                Incidencia.reportado_por.ilike(patron),
                TipoFalla.nombre.ilike(patron),
                Equipo.nombre.ilike(patron),
            )
        )
    return query


def list_incidencias(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    **filtros,
):
    query = _query_incidencias_filtrada(db, **filtros).options(*CARGA_RELACIONES)
    return query.order_by(Incidencia.fecha_reporte.desc()).offset(skip).limit(limit).all()


def count_incidencias(db: Session, **filtros) -> int:
    """Total que cumple los filtros, ignorando skip/limit (para armar la paginacion)."""
    return _query_incidencias_filtrada(db, **filtros).count()


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
    db: Session,
    equipo: Equipo,
    tipo_falla: TipoFalla,
    reportado_por: str,
    gravedad: str,
    funcional: bool,
    descripcion: Optional[str] = None,
) -> Incidencia:
    """Portal de Reporte Express: fecha/hora y origen='qr' quedan registrados automaticamente.

    La prioridad NO sale de tipo_falla.prioridad_base aqui (esa queda para incidencias
    creadas por IA/tecnico) -- para el reporte publico la decide quien reporta:
    leve -> baja, grave -> alta, y si marca que el equipo ya no funciona, urgente siempre
    (pisando la gravedad elegida) y el equipo pasa a 'fuera_de_servicio' de inmediato, sin
    esperar a que un tecnico lo revise.
    """
    if not funcional:
        prioridad = PrioridadIncidencia.urgente
    elif gravedad == "grave":
        prioridad = PrioridadIncidencia.alta
    else:
        prioridad = PrioridadIncidencia.baja

    qr_activo = equipo.qr_activo
    incidencia = _crear_incidencia(
        db,
        equipo_id=equipo.id,
        tipo_falla=tipo_falla,
        origen=OrigenIncidencia.qr,
        reportado_por=reportado_por,
        descripcion=descripcion,
        prioridad=prioridad,
        qr_id=qr_activo.id if qr_activo else None,
    )

    if not funcional and equipo.estado != EstadoEquipo.fuera_de_servicio:
        equipo.estado = EstadoEquipo.fuera_de_servicio
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
