from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.gymkeep import EstadoCamara


class CamaraBase(BaseModel):
    codigo: str
    nombre: str
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    ip: Optional[str] = None
    rtsp_url: Optional[str] = None


class CamaraCreate(CamaraBase):
    sucursal_id: int
    zona_id: Optional[int] = None
    equipo_ids: list[int] = []


class CamaraOut(CamaraBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    zona_id: Optional[int] = None
    estado: EstadoCamara
    created_at: datetime
