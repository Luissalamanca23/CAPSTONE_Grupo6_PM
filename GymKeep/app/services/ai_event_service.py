from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from pymongo.errors import DuplicateKeyError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.mongo import get_mongo_db
from app.models.gymkeep import (
    EventoIAResumen,
    OrigenUso,
    SesionUso,
    TipoEventoIA,
)
from app.schemas.ai_event import EventoIACreate

EVENTOS_DE_USO = (TipoEventoIA.inicio_uso, TipoEventoIA.uso_en_curso, TipoEventoIA.fin_uso)

# Datos de la sesion que calcula el pipeline de vision y que conviene conservar en
# sesiones_uso.metadata (tiempo real sobre la maquina, pausas, motivo de cierre).
METADATA_SESION = (
    "sesion_ref",
    "maquina",
    "presencia_segundos",
    "pausas",
    "pausa_max_segundos",
    "personas_max",
    "cierre",
)


def guardar_evento_ia(db: Session, evento: EventoIACreate) -> EventoIAResumen:
    """
    1) Guarda el documento completo en MongoDB (coleccion `eventos_ia`).
    2) Guarda un resumen consultable en PostgreSQL (`eventos_ia_resumen`).
    3) Si es un evento de uso (inicio_uso / uso_en_curso / fin_uso), lo consolida en
       `sesiones_uso`: el inicio abre una sesion, el fin la cierra con su duracion.

    Este es el puente descrito en GymKeep_BDD_Completa/README.md: la base de datos oficial
    del negocio (Postgres) solo necesita saber que el evento existe y su resultado; el
    detalle de detecciones/tracking vive en MongoDB.

    Es idempotente por `event_uuid`: si el pipeline reintenta un envio (timeout, corte de
    red), se devuelve el resumen ya guardado sin duplicar nada.
    """
    existente = (
        db.query(EventoIAResumen).filter(EventoIAResumen.evento_uuid == evento.event_uuid).first()
    )
    if existente:
        return existente

    mongo = get_mongo_db()

    doc = evento.model_dump(mode="python")
    doc["event_uuid"] = str(evento.event_uuid)

    try:
        mongo.eventos_ia.insert_one(doc)
    except DuplicateKeyError:
        # Quedo en Mongo en un intento anterior que fallo antes de llegar a Postgres.
        pass

    evidencia = evento.evidencia
    tipo_evento = TipoEventoIA(evento.evento.tipo)

    resumen = EventoIAResumen(
        evento_uuid=evento.event_uuid,
        equipo_id=evento.equipo_id,
        camara_id=evento.camara_id,
        modelo_ia_id=evento.modelo.id,
        sesion_uso_id=evento.sesion_uso_id,
        tipo_evento=tipo_evento,
        timestamp_evento=evento.timestamp,
        confidence=Decimal(str(evento.evento.confidence)) if evento.evento.confidence is not None else None,
        mongo_collection="eventos_ia",
        snapshot_url=evidencia.snapshot_url if evidencia else None,
        clip_url=evidencia.clip_url if evidencia else None,
    )
    db.add(resumen)

    if tipo_evento in EVENTOS_DE_USO and evento.equipo_id is not None:
        sesion = _consolidar_sesion_uso(db, evento, tipo_evento)
        if sesion is not None:
            resumen.sesion_uso_id = sesion.id
            resumen.procesado = True

    db.commit()
    db.refresh(resumen)
    return resumen


def _consolidar_sesion_uso(db: Session, evento: EventoIACreate, tipo: TipoEventoIA) -> SesionUso | None:
    """Etapa 4 de §6.6.1 del estudio: pares inicio_uso / fin_uso -> una fila en sesiones_uso.

    La histeresis (T_on / T_off) ya la aplico el pipeline; aqui solo se abre, se sostiene
    y se cierra la sesion. Devuelve None si el evento no corresponde a ninguna sesion
    (ej. un fin_uso sin inicio): el resumen queda con procesado = FALSE para revisarlo."""
    abierta = (
        db.query(SesionUso)
        .filter(
            SesionUso.equipo_id == evento.equipo_id,
            SesionUso.camara_id == evento.camara_id,
            SesionUso.estado == "abierta",
        )
        .order_by(SesionUso.fecha_inicio.desc())
        .first()
    )
    confianza = evento.evento.confidence
    metadata = {k: evento.metadata[k] for k in METADATA_SESION if k in evento.metadata}

    if tipo == TipoEventoIA.inicio_uso:
        if abierta is not None:
            _cerrar_sesion_huerfana(db, abierta)
        sesion = iniciar_sesion_uso(
            db,
            equipo_id=evento.equipo_id,
            camara_id=evento.camara_id,
            modelo_ia_id=evento.modelo.id,
            evento_inicio_uuid=evento.event_uuid,
            fecha_inicio=evento.timestamp,
            confidence=confianza,
        )
        sesion.metadata_json = metadata
        return sesion

    if abierta is None:
        return None

    if tipo == TipoEventoIA.uso_en_curso:
        abierta.cantidad_eventos += 1
        if confianza is not None:
            previa = float(abierta.confianza_promedio) if abierta.confianza_promedio is not None else confianza
            n = abierta.cantidad_eventos
            abierta.confianza_promedio = round(previa + (confianza - previa) / n, 4)
        return abierta

    # fin_uso: la confianza que manda el pipeline es el promedio de toda la sesion
    # (calculado cuadro a cuadro), mas representativo que promediar solo los eventos.
    finalizar_sesion_uso(
        db,
        abierta,
        evento_fin_uuid=evento.event_uuid,
        fecha_fin=evento.timestamp,
        cantidad_eventos=abierta.cantidad_eventos + 1,
        confianza_promedio=confianza,
    )
    abierta.metadata_json = {**(abierta.metadata_json or {}), **metadata}
    return abierta


def _cerrar_sesion_huerfana(db: Session, sesion: SesionUso) -> None:
    """Llega un inicio_uso con una sesion todavia abierta en la misma maquina y camara:
    el fin_uso anterior se perdio (reinicio del pipeline, corte de red). Se aplica la
    regla del watchdog de §6.6.5: si hubo eventos intermedios se cierra en el ultimo
    evento recibido; si solo hubo inicio, se descarta (no se imputa uso no observado)."""
    if sesion.cantidad_eventos > 1:
        ultimo = (
            db.query(func.max(EventoIAResumen.timestamp_evento))
            .filter(EventoIAResumen.sesion_uso_id == sesion.id)
            .scalar()
        )
        sesion.fecha_fin = ultimo or sesion.fecha_inicio
        sesion.estado = "cerrada"
        sesion.duracion_segundos = _segundos_entre(sesion.fecha_inicio, sesion.fecha_fin)
        sesion.metadata_json = {**(sesion.metadata_json or {}), "cierre": "forzado"}
    else:
        sesion.estado = "descartada"
        sesion.metadata_json = {
            **(sesion.metadata_json or {}),
            "motivo": "sin_evidencia_de_continuidad",
        }


def _segundos_entre(inicio: datetime, fin: datetime) -> int:
    # Postgres devuelve fechas con zona horaria; SQLite (tests) las devuelve sin ella.
    if inicio.tzinfo is None or fin.tzinfo is None:
        inicio, fin = inicio.replace(tzinfo=None), fin.replace(tzinfo=None)
    return max(0, int((fin - inicio).total_seconds()))


def iniciar_sesion_uso(
    db: Session,
    *,
    equipo_id: int,
    camara_id: int,
    modelo_ia_id: int | None,
    evento_inicio_uuid: UUID,
    fecha_inicio: datetime | None = None,
    confidence: float | None = None,
) -> SesionUso:
    """Abre una sesion de uso. Hace flush (no commit): el llamador confirma la transaccion
    junto con el evento que la origino."""
    sesion = SesionUso(
        equipo_id=equipo_id,
        camara_id=camara_id,
        modelo_ia_id=modelo_ia_id,
        origen=OrigenUso.ia,
        fecha_inicio=fecha_inicio or datetime.now(timezone.utc),
        evento_inicio_uuid=evento_inicio_uuid,
        confianza_promedio=confidence,
        cantidad_eventos=1,
        estado="abierta",
    )
    db.add(sesion)
    db.flush()
    return sesion


def finalizar_sesion_uso(
    db: Session,
    sesion: SesionUso,
    *,
    evento_fin_uuid: UUID,
    fecha_fin: datetime | None = None,
    cantidad_eventos: int | None = None,
    confianza_promedio: float | None = None,
) -> SesionUso:
    """Cierra una sesion de uso. Hace flush (no commit), igual que iniciar_sesion_uso."""
    sesion.fecha_fin = fecha_fin or datetime.now(timezone.utc)
    sesion.evento_fin_uuid = evento_fin_uuid
    sesion.estado = "cerrada"

    if cantidad_eventos is not None:
        sesion.cantidad_eventos = cantidad_eventos

    if confianza_promedio is not None:
        sesion.confianza_promedio = confianza_promedio

    # Duracion: el trigger de PostgreSQL (set_duracion_sesion_uso) tambien la calcula.
    sesion.duracion_segundos = _segundos_entre(sesion.fecha_inicio, sesion.fecha_fin)

    db.flush()
    return sesion
