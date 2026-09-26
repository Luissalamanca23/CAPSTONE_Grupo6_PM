from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import EstadoEquipo, Equipo, SesionUso


def list_sesiones_uso(
    db: Session,
    equipo_id: Optional[int] = None,
    estado: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    query = db.query(SesionUso)
    if equipo_id is not None:
        query = query.filter(SesionUso.equipo_id == equipo_id)
    if estado is not None:
        query = query.filter(SesionUso.estado == estado)
    return query.order_by(SesionUso.fecha_inicio.desc()).offset(skip).limit(limit).all()


def _segundos_union(intervalos: list[tuple[datetime, datetime]]) -> float:
    """Medida de la union de intervalos: lo que se solapa se cuenta una sola vez."""
    total = 0.0
    bloque_ini = bloque_fin = None
    for ini, fin in sorted(intervalos):
        if bloque_fin is None or ini > bloque_fin:
            if bloque_fin is not None:
                total += (bloque_fin - bloque_ini).total_seconds()
            bloque_ini, bloque_fin = ini, fin
        else:
            bloque_fin = max(bloque_fin, fin)
    if bloque_fin is not None:
        total += (bloque_fin - bloque_ini).total_seconds()
    return total


def horometro(db: Session, equipo_id: Optional[int] = None, desde: Optional[datetime] = None) -> list[dict]:
    """Horas de uso por equipo a partir de las sesiones cerradas (§6.6.4 del estudio).
    `desde` permite medir, por ejemplo, las horas desde el ultimo mantenimiento."""
    equipos = db.query(Equipo).filter(Equipo.estado != EstadoEquipo.retirado)
    sesiones = db.query(SesionUso).filter(SesionUso.estado == "cerrada", SesionUso.fecha_fin.isnot(None))
    if equipo_id is not None:
        equipos = equipos.filter(Equipo.id == equipo_id)
        sesiones = sesiones.filter(SesionUso.equipo_id == equipo_id)
    if desde is not None:
        sesiones = sesiones.filter(SesionUso.fecha_inicio >= desde)

    por_equipo: dict[int, list[SesionUso]] = {}
    for sesion in sesiones.all():
        por_equipo.setdefault(sesion.equipo_id, []).append(sesion)

    resultado = []
    for equipo in equipos.order_by(Equipo.id).all():
        propias = por_equipo.get(equipo.id, [])
        intervalos = [(s.fecha_inicio, s.fecha_fin) for s in propias]
        resultado.append(
            {
                "equipo_id": equipo.id,
                "codigo_activo": equipo.codigo_activo,
                "nombre": equipo.nombre,
                "sesiones_cerradas": len(propias),
                "horas_uso": round(_segundos_union(intervalos) / 3600, 4),
                "horas_suma": round(sum((s.duracion_segundos or 0) for s in propias) / 3600, 4),
                "ultima_sesion": max((s.fecha_fin for s in propias), default=None),
            }
        )
    return resultado
