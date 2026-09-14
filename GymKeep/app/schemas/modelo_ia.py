from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ModeloIABase(BaseModel):
    nombre: str
    version: str
    framework: Optional[str] = None
    tipo_modelo: Optional[str] = None
    clases: list[str] = []
    metricas: dict[str, Any] = {}


class ModeloIACreate(ModeloIABase):
    pass


class ModeloIAOut(ModeloIABase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activo: bool
    created_at: datetime
