"""Eliminacion en cascada de datos desde el panel (maquinas, zonas, camaras, sucursales,
reportes y mantenimientos).

Por que no basta `db.delete(obj)`: el esquema define varias FK con ON DELETE RESTRICT
(equipos -> incidencias / mantenimientos / sesiones_uso, camaras -> eventos_ia_resumen) para
proteger el historial, asi que borrar un equipo con datos falla. Desde el panel el operador
puede pedir borrar igual (p. ej. limpiar datos de prueba): aqui se borran los hijos en el
orden correcto, dentro de UNA transaccion de Postgres, y luego se limpia Mongo (eventos IA,
telemetria, estado en vivo y fotos) como mejor esfuerzo.

Cada `resumen_*` devuelve los conteos de lo que se llevaria el borrado; el panel los muestra
en el dialogo de confirmacion antes de llamar al DELETE con `forzar=true`.
"""

import logging
from typing import Iterable, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.mongo import get_mongo_db
from app.models.gymkeep import (
    Camara,
    Equipo,
    EventoIAResumen,
    Incidencia,
    Mantenimiento,
    QrEquipo,
    RegistroAuditoria,
    SesionUso,
    Sucursal,
    Zona,
    camara_equipos,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- utilidades


def _contar(db: Session, tabla_col, ids: Iterable[int]) -> int:
    ids = list(ids)
    if not ids:
        return 0
    return db.scalar(select(func.count()).select_from(tabla_col.class_).where(tabla_col.in_(ids))) or 0


def _ids(db: Session, columna_id, condicion) -> list[int]:
    return list(db.scalars(select(columna_id).where(condicion)))


def _limpiar_mongo(equipo_ids: list[int], camara_ids: list[int]) -> bool:
    """Borra lo de Mongo asociado a esas maquinas/camaras. Devuelve False si fallo (el borrado
    de Postgres ya quedo hecho; lo huerfano de Mongo es inofensivo y se puede vaciar luego
    con mongo/limpiar_datos_pruebas.js)."""
    if not equipo_ids and not camara_ids:
        return True
    try:
        mongo = get_mongo_db()
        if camara_ids:
            mongo.camaras_vivo.delete_many({"_id": {"$in": camara_ids}})
            for coleccion in ("eventos_ia", "detecciones_raw", "telemetria_camaras"):
                getattr(mongo, coleccion).delete_many({"camara_id": {"$in": camara_ids}})
        if equipo_ids:
            mongo.fotos_equipos.delete_many({"_id": {"$in": equipo_ids}})
            mongo.eventos_ia.delete_many({"equipo_id": {"$in": equipo_ids}})
        return True
    except Exception:  # noqa: BLE001 - mejor esfuerzo, no debe deshacer el borrado SQL
        logger.exception("No se pudo limpiar Mongo tras eliminar datos")
        return False


# ------------------------------------------------------------- borrado interno (sin commit)


def _borrar_camaras(db: Session, camara_ids: list[int]) -> None:
    if not camara_ids:
        return
    db.execute(delete(EventoIAResumen).where(EventoIAResumen.camara_id.in_(camara_ids)))
    db.execute(update(SesionUso).where(SesionUso.camara_id.in_(camara_ids)).values(camara_id=None))
    db.execute(update(Incidencia).where(Incidencia.camara_id.in_(camara_ids)).values(camara_id=None))
    db.execute(delete(camara_equipos).where(camara_equipos.c.camara_id.in_(camara_ids)))
    db.execute(delete(Camara).where(Camara.id.in_(camara_ids)))


def _borrar_equipos(db: Session, equipo_ids: list[int]) -> None:
    if not equipo_ids:
        return
    db.execute(delete(EventoIAResumen).where(EventoIAResumen.equipo_id.in_(equipo_ids)))
    db.execute(delete(Mantenimiento).where(Mantenimiento.equipo_id.in_(equipo_ids)))
    db.execute(delete(Incidencia).where(Incidencia.equipo_id.in_(equipo_ids)))
    db.execute(delete(SesionUso).where(SesionUso.equipo_id.in_(equipo_ids)))
    db.execute(delete(camara_equipos).where(camara_equipos.c.equipo_id.in_(equipo_ids)))
    db.execute(delete(QrEquipo).where(QrEquipo.equipo_id.in_(equipo_ids)))
    db.execute(delete(Equipo).where(Equipo.id.in_(equipo_ids)))


# ------------------------------------------------------------------------------ maquinas


def resumen_equipo(db: Session, equipo_id: int) -> dict:
    ids = [equipo_id]
    return {
        "incidencias": _contar(db, Incidencia.equipo_id, ids),
        "mantenimientos": _contar(db, Mantenimiento.equipo_id, ids),
        "sesiones_uso": _contar(db, SesionUso.equipo_id, ids),
        "eventos_ia": _contar(db, EventoIAResumen.equipo_id, ids),
        "codigos_qr": _contar(db, QrEquipo.equipo_id, ids),
    }


def eliminar_equipo(db: Session, equipo_id: int) -> bool:
    _borrar_equipos(db, [equipo_id])
    db.commit()
    return _limpiar_mongo([equipo_id], [])


# --------------------------------------------------------------------------------- zonas


def resumen_zona(db: Session, zona_id: int) -> dict:
    return {
        "maquinas_sin_zona": _contar(db, Equipo.zona_id, [zona_id]),
        "camaras_sin_zona": _contar(db, Camara.zona_id, [zona_id]),
    }


def eliminar_zona(db: Session, zona_id: int) -> None:
    """La zona se borra; sus maquinas y camaras se conservan, solo quedan 'sin zona'."""
    db.execute(update(Equipo).where(Equipo.zona_id == zona_id).values(zona_id=None))
    db.execute(update(Camara).where(Camara.zona_id == zona_id).values(zona_id=None))
    db.execute(delete(Zona).where(Zona.id == zona_id))
    db.commit()


# ------------------------------------------------------------------------------- camaras


def resumen_camara(db: Session, camara_id: int) -> dict:
    return {
        "eventos_ia": _contar(db, EventoIAResumen.camara_id, [camara_id]),
        "maquinas_vinculadas": db.scalar(
            select(func.count()).select_from(camara_equipos).where(camara_equipos.c.camara_id == camara_id)
        )
        or 0,
        "sesiones_uso_desvinculadas": _contar(db, SesionUso.camara_id, [camara_id]),
    }


def eliminar_camara(db: Session, camara_id: int) -> bool:
    _borrar_camaras(db, [camara_id])
    db.commit()
    return _limpiar_mongo([], [camara_id])


# ----------------------------------------------------------------------------- sucursales


def resumen_sucursal(db: Session, sucursal_id: int) -> dict:
    equipo_ids = _ids(db, Equipo.id, Equipo.sucursal_id == sucursal_id)
    camara_ids = _ids(db, Camara.id, Camara.sucursal_id == sucursal_id)
    return {
        "zonas": _contar(db, Zona.sucursal_id, [sucursal_id]),
        "maquinas": len(equipo_ids),
        "camaras": len(camara_ids),
        "incidencias": _contar(db, Incidencia.equipo_id, equipo_ids),
        "mantenimientos": _contar(db, Mantenimiento.equipo_id, equipo_ids),
        "sesiones_uso": _contar(db, SesionUso.equipo_id, equipo_ids),
        "eventos_ia": _contar(db, EventoIAResumen.camara_id, camara_ids),
    }


def eliminar_sucursal(db: Session, sucursal_id: int) -> bool:
    equipo_ids = _ids(db, Equipo.id, Equipo.sucursal_id == sucursal_id)
    camara_ids = _ids(db, Camara.id, Camara.sucursal_id == sucursal_id)
    _borrar_equipos(db, equipo_ids)
    _borrar_camaras(db, camara_ids)
    db.execute(update(RegistroAuditoria).where(RegistroAuditoria.sucursal_id == sucursal_id).values(sucursal_id=None))
    db.execute(delete(Zona).where(Zona.sucursal_id == sucursal_id))
    db.execute(delete(Sucursal).where(Sucursal.id == sucursal_id))
    db.commit()
    return _limpiar_mongo(equipo_ids, camara_ids)


# ------------------------------------------------------------- reportes y mantenimientos


def resumen_incidencia(db: Session, incidencia_id: int) -> dict:
    return {"mantenimientos_desvinculados": _contar(db, Mantenimiento.incidencia_id, [incidencia_id])}


def eliminar_incidencia(db: Session, incidencia_id: int) -> None:
    """Borra el reporte; los mantenimientos que lo mencionaban se conservan sin vinculo."""
    db.execute(update(Mantenimiento).where(Mantenimiento.incidencia_id == incidencia_id).values(incidencia_id=None))
    db.execute(delete(Incidencia).where(Incidencia.id == incidencia_id))
    db.commit()


def eliminar_mantenimiento(db: Session, mantenimiento_id: int) -> None:
    db.execute(delete(Mantenimiento).where(Mantenimiento.id == mantenimiento_id))
    db.commit()


def respuesta_resumen(entidad: str, nombre: Optional[str], conteos: dict) -> dict:
    """Forma comun que consume el dialogo de confirmacion del panel."""
    return {"entidad": entidad, "nombre": nombre, "conteos": conteos, "total_dependientes": sum(conteos.values())}
