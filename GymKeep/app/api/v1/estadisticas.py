from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.gymkeep import Equipo, EstadoEquipo, EstadoIncidencia, Incidencia, PrioridadIncidencia

router = APIRouter()


@router.get("/")
def obtener_estadisticas(db: Session = Depends(get_db)):
    """Conteos agregados para el panel de gestion, calculados con GROUP BY en la base
    (no dependen de listas truncadas por `limit`). Todas las claves de estado y prioridad
    vienen siempre, con 0 si no hay registros."""
    por_estado_equipo = dict(db.query(Equipo.estado, func.count(Equipo.id)).group_by(Equipo.estado).all())
    por_estado_incidencia = dict(
        db.query(Incidencia.estado, func.count(Incidencia.id)).group_by(Incidencia.estado).all()
    )
    abiertas_por_prioridad = dict(
        db.query(Incidencia.prioridad, func.count(Incidencia.id))
        .filter(Incidencia.estado.in_([EstadoIncidencia.pendiente, EstadoIncidencia.en_proceso]))
        .group_by(Incidencia.prioridad)
        .all()
    )

    equipos_por_estado = {e.value: por_estado_equipo.get(e, 0) for e in EstadoEquipo}
    incidencias_por_estado = {e.value: por_estado_incidencia.get(e, 0) for e in EstadoIncidencia}
    return {
        "equipos_total": sum(equipos_por_estado.values()),
        "equipos_por_estado": equipos_por_estado,
        "incidencias_por_estado": incidencias_por_estado,
        "incidencias_abiertas": incidencias_por_estado["pendiente"] + incidencias_por_estado["en_proceso"],
        "incidencias_abiertas_por_prioridad": {
            p.value: abiertas_por_prioridad.get(p, 0) for p in PrioridadIncidencia
        },
    }
