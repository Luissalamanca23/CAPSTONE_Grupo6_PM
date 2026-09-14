from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.gymkeep import EstadoSucursal


class SucursalBase(BaseModel):
    codigo: str
    nombre: str
    direccion: Optional[str] = None
    comuna: Optional[str] = None
    ciudad: Optional[str] = None
    region: Optional[str] = None


class SucursalCreate(SucursalBase):
    empresa_id: int


class SucursalOut(SucursalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    estado: EstadoSucursal
    created_at: datetime
