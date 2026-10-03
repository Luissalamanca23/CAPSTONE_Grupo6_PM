from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.gymkeep import Equipo, EstadoIncidencia, Incidencia, Mantenimiento


def listar_mantenimientos(
    db: Session,
    *,
    equipo_id: Optional[int] = None,
    tipo: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    q: Optional[str] = None,
) -> List[Mantenimiento]:
    """Historial de mantenimientos. Sin `equipo_id` devuelve el historial de TODO el
    gimnasio (usado por la vista de Costos de mantencion); con `equipo_id` queda igual que
    antes (usado por el detalle de un equipo)."""
    query = db.query(Mantenimiento).options(joinedload(Mantenimiento.equipo))
    if equipo_id is not None:
        query = query.filter(Mantenimiento.equipo_id == equipo_id)
    if tipo:
        query = query.filter(Mantenimiento.tipo == tipo)
    if fecha_desde is not None:
        query = query.filter(Mantenimiento.fecha_inicio >= fecha_desde)
    if fecha_hasta is not None:
        query = query.filter(Mantenimiento.fecha_inicio < fecha_hasta + timedelta(days=1))
    if q:
        patron = f"%{q.strip()}%"
        query = query.join(Equipo, Mantenimiento.equipo_id == Equipo.id).filter(
            or_(
                Mantenimiento.tecnico.ilike(patron),
                Mantenimiento.descripcion.ilike(patron),
                Equipo.nombre.ilike(patron),
            )
        )
    return query.order_by(Mantenimiento.fecha_inicio.desc()).all()


def crear_mantenimiento(
    db: Session,
    equipo: Equipo,
    tipo: str,
    tecnico: str,
    descripcion: str,
    incidencia_ids: List[int],
    costo_total: Optional[float] = None,
) -> List[Mantenimiento]:
    """Registra el mantenimiento ya realizado.

    La tabla `mantenimientos` liga cada fila a UNA incidencia (no a varias): si el tecnico
    resuelve varias fallas de una vez se crea un registro por cada incidencia (mismos datos
    de tecnico/descripcion/fecha), y cada una de esas incidencias queda marcada como
    resuelta. Si no se asocia a ninguna incidencia especifica (mantenimiento preventivo o
    revision general del equipo), se crea un unico registro con incidencia_id=None.

    Solo se aceptan incidencias que de verdad son de este equipo y que siguen abiertas
    (pendiente/en_proceso) -- pedir resolver una ya resuelta, o de otro equipo, se ignora en
    silencio en vez de fallar, para no trabar el formulario si la lista quedo desactualizada.

    El costo ingresado es UNO solo por visita/registro del tecnico, pero si esa visita deja
    resueltas varias incidencias se crea una fila de `mantenimientos` por cada una (ver mas
    abajo). Para que sumar `costo_total` de "gastos de mantencion" no cuente el mismo gasto
    varias veces, el costo se guarda solo en la PRIMERA fila del lote; el resto queda en None.
    """
    ahora = datetime.now(timezone.utc)

    incidencias_validas: List[Incidencia] = []
    if incidencia_ids:
        incidencias_validas = (
            db.query(Incidencia)
            .filter(
                Incidencia.id.in_(incidencia_ids),
                Incidencia.equipo_id == equipo.id,
                Incidencia.estado.in_((EstadoIncidencia.pendiente, EstadoIncidencia.en_proceso)),
            )
            .all()
        )

    registros: List[Mantenimiento] = []

    if incidencias_validas:
        for indice, incidencia in enumerate(incidencias_validas):
            registro = Mantenimiento(
                equipo_id=equipo.id,
                incidencia_id=incidencia.id,
                tipo=tipo,
                tecnico=tecnico,
                descripcion=descripcion,
                costo_total=costo_total if indice == 0 else None,
                fecha_inicio=ahora,
                fecha_fin=ahora,
            )
            db.add(registro)
            registros.append(registro)
            incidencia.estado = EstadoIncidencia.resuelta
            incidencia.fecha_resolucion = ahora
    else:
        registro = Mantenimiento(
            equipo_id=equipo.id,
            incidencia_id=None,
            tipo=tipo,
            tecnico=tecnico,
            descripcion=descripcion,
            costo_total=costo_total,
            fecha_inicio=ahora,
            fecha_fin=ahora,
        )
        db.add(registro)
        registros.append(registro)

    db.commit()
    for registro in registros:
        db.refresh(registro)

    return registros
