"""Foto opcional del dano/falla que adjunta quien reporta por QR.

Donde queda: MongoDB, coleccion `fotos_incidencias` (un documento por incidencia, `_id` =
id de la incidencia en PostgreSQL), igual que las fotos de referencia de las maquinas
(`fotos_equipos`). Postgres no cambia: sin migracion.

La foto es OPCIONAL y de mejor esfuerzo: si Mongo falla el reporte igual se crea (solo
queda sin foto). Lo que si se valida antes de crear el reporte es que la imagen sea valida,
para avisarle al usuario en vez de perderla en silencio.
"""

from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from bson import Binary

from app.core.mongo import get_mongo_db
from app.services.vision_service import ImagenInvalida, _a_jpeg

logger = logging.getLogger(__name__)

MAX_LADO_FOTO_INCIDENCIA = 1280
# Tope del texto base64 recibido (~6 MB de imagen). El formulario ya la achica en el celular.
MAX_BASE64_CHARS = 8_000_000


def decodificar(foto_b64: str) -> bytes:
    """Acepta base64 puro o un data URL (`data:image/jpeg;base64,...`)."""
    texto = foto_b64.strip()
    if texto.startswith("data:"):
        _, _, texto = texto.partition(",")
    try:
        return base64.b64decode(texto, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ImagenInvalida("La foto no se pudo leer.") from exc


def preparar(foto_b64: str) -> tuple[bytes, int, int]:
    """Valida la foto y la deja en JPEG de a lo mas 1280 px. Lanza ImagenInvalida."""
    return _a_jpeg(decodificar(foto_b64), MAX_LADO_FOTO_INCIDENCIA)


def guardar(incidencia_id: int, jpeg: bytes, ancho: int, alto: int) -> bool:
    try:
        get_mongo_db().fotos_incidencias.replace_one(
            {"_id": incidencia_id},
            {
                "_id": incidencia_id,
                "imagen": Binary(jpeg),
                "ancho": ancho,
                "alto": alto,
                "creada": datetime.now(timezone.utc),
            },
            upsert=True,
        )
        return True
    except Exception:  # noqa: BLE001 - la foto es opcional, no debe tumbar el reporte
        logger.exception("No se pudo guardar la foto de la incidencia %s", incidencia_id)
        return False


def leer(incidencia_id: int) -> Optional[bytes]:
    doc = get_mongo_db().fotos_incidencias.find_one({"_id": incidencia_id}, {"imagen": 1})
    return bytes(doc["imagen"]) if doc else None


def con_foto(incidencia_ids: Iterable[int]) -> set[int]:
    """Ids (de los dados) que tienen foto. Si Mongo no responde, ninguno (el listado sigue)."""
    ids = list(incidencia_ids)
    if not ids:
        return set()
    try:
        docs = get_mongo_db().fotos_incidencias.find({"_id": {"$in": ids}}, {"_id": 1})
        return {d["_id"] for d in docs}
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo consultar las fotos de incidencias")
        return set()


def borrar(incidencia_ids: Iterable[int]) -> bool:
    ids = list(incidencia_ids)
    if not ids:
        return True
    try:
        get_mongo_db().fotos_incidencias.delete_many({"_id": {"$in": ids}})
        return True
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo borrar fotos de incidencias")
        return False


def anotar(incidencias) -> None:
    """Marca `tiene_foto` en cada incidencia (atributo transitorio que lee IncidenciaOut)."""
    incidencias = list(incidencias)
    con = con_foto(i.id for i in incidencias)
    for incidencia in incidencias:
        incidencia.tiene_foto = incidencia.id in con
