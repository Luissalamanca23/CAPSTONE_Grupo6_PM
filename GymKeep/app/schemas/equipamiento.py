from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.gymkeep import EstadoEquipo


class SucursalMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    codigo: str


class ZonaMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class QrEquipoOut(BaseModel):
    """El QR es una entidad propia del equipo (no un campo fijo): puede revocarse y
    reemitirse sin perder el historial de codigos anteriores."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token: UUID
    activo: bool
    fecha_emision: datetime
    fecha_expiracion: Optional[datetime] = None


class EquipoBase(BaseModel):
    codigo_activo: str = Field(..., description="Codigo interno/de activo del equipo (ej. EQ-0001).")
    nombre: str
    categoria: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    fecha_adquisicion: Optional[date] = None
    fecha_instalacion: Optional[date] = None
    vida_util_meses: Optional[int] = Field(default=None, gt=0)
    observaciones: Optional[str] = None
    estado: EstadoEquipo = EstadoEquipo.operativo


class EquipoCreate(EquipoBase):
    sucursal_id: int
    zona_id: Optional[int] = None


class EquipoUpdate(BaseModel):
    zona_id: Optional[int] = None
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    observaciones: Optional[str] = None
    estado: Optional[EstadoEquipo] = None


class EquipoOut(EquipoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    zona_id: Optional[int] = None
    created_at: datetime
    sucursal: Optional[SucursalMini] = None
    zona: Optional[ZonaMini] = None
    qr_activo: Optional[QrEquipoOut] = None
