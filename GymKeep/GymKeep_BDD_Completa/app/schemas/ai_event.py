from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ModeloEventoIA(BaseModel):
    id: Optional[int] = None
    nombre: str
    version: str


class EventoDetalleIA(BaseModel):
    tipo: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class EvidenciaIA(BaseModel):
    snapshot_url: Optional[str] = None
    clip_url: Optional[str] = None


class EventoIACreate(BaseModel):
    event_uuid: UUID
    timestamp: datetime

    empresa_id: Optional[int] = None
    sucursal_id: Optional[int] = None
    zona_id: Optional[int] = None
    camara_id: int
    equipo_id: Optional[int] = None
    sesion_uso_id: Optional[int] = None

    modelo: ModeloEventoIA
    evento: EventoDetalleIA
    detecciones: list[dict[str, Any]] = []
    tracking: Optional[dict[str, Any]] = None
    evidencia: Optional[EvidenciaIA] = None
    metadata: dict[str, Any] = {}
