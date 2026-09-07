from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.equipamiento import EstadoEquipo


class EquipoBase(BaseModel):
    codigo_qr: str
    nombre: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    ubicacion: Optional[str] = None
    estado: EstadoEquipo = EstadoEquipo.operativo


class EquipoCreate(EquipoBase):
    pass


class EquipoUpdate(BaseModel):
    nombre: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    ubicacion: Optional[str] = None
    estado: Optional[EstadoEquipo] = None


class EquipoOut(EquipoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_registro: datetime
