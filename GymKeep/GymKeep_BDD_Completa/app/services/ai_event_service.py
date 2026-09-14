from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.mongo import get_mongo_db
from app.models.gymkeep import (
    EventoIAResumen,
    OrigenUso,
    SesionUso,
    TipoEventoIA,
)
from app.schemas.ai_event import EventoIACreate


def guardar_evento_ia(db: Session, evento: EventoIACreate) -> EventoIAResumen:
    """
    1) Guarda el documento completo en MongoDB.
    2) Guarda un resumen consultable en PostgreSQL.
    """
    mongo = get_mongo_db()

    doc = evento.model_dump(mode="python")
    doc["event_uuid"] = str(evento.event_uuid)

    # PyMongo acepta datetime, pero UUID se normaliza a string para simplificar integración.
    mongo.eventos_ia.insert_one(doc)

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
    db.commit()
    db.refresh(resumen)
    return resumen


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
    db.commit()
    db.refresh(sesion)
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
    sesion.fecha_fin = fecha_fin or datetime.now(timezone.utc)
    sesion.evento_fin_uuid = evento_fin_uuid
    sesion.estado = "cerrada"

    if cantidad_eventos is not None:
        sesion.cantidad_eventos = cantidad_eventos

    if confianza_promedio is not None:
        sesion.confianza_promedio = confianza_promedio

    # Duración: el trigger de PostgreSQL también la calcula.
    sesion.duracion_segundos = max(
        0,
        int((sesion.fecha_fin - sesion.fecha_inicio).total_seconds())
    )

    db.commit()
    db.refresh(sesion)
    return sesion
