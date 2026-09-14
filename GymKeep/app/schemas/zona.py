from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ZonaBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    piso: Optional[str] = None


class ZonaCreate(ZonaBase):
    sucursal_id: int


class ZonaOut(ZonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    activa: bool
    created_at: datetime
