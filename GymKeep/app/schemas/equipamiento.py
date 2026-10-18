from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.gymkeep import EstadoEquipo


# Categorias de equipo del gimnasio (mismo orden que frontend/src/components/CategoriaEquipoBadge.jsx).
# Solo se validan al ESCRIBIR (crear/editar): los equipos antiguos con otra categoria (p. ej.
# "fuerza") se siguen leyendo sin error hasta que se reclasifican.
CATEGORIAS_EQUIPO = ("cardio", "placas", "discos", "peso_libre", "bancos_racks", "funcional")


def _validar_categoria(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    valor = valor.strip()
    if not valor:
        return None
    if valor not in CATEGORIAS_EQUIPO:
        raise ValueError(f"Categoria no valida. Use una de: {', '.join(CATEGORIAS_EQUIPO)}.")
    return valor


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

    _categoria_valida = field_validator("categoria")(_validar_categoria)


class EquipoUpdate(BaseModel):
    """Edicion parcial desde el panel: solo se cambian los campos enviados. `zona_id: null`
    deja la maquina sin zona; en los campos obligatorios (codigo, nombre, estado) un null se ignora."""

    zona_id: Optional[int] = None
    codigo_activo: Optional[str] = Field(default=None, min_length=1, max_length=64)
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=120)
    categoria: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    numero_serie: Optional[str] = None
    fecha_adquisicion: Optional[date] = None
    fecha_instalacion: Optional[date] = None
    vida_util_meses: Optional[int] = Field(default=None, gt=0)
    observaciones: Optional[str] = None
    estado: Optional[EstadoEquipo] = None

    _categoria_valida = field_validator("categoria")(_validar_categoria)

    @field_validator("numero_serie", "marca", "modelo", "observaciones")
    @classmethod
    def _texto_vacio_es_nulo(cls, valor: Optional[str]) -> Optional[str]:
        # Un campo vaciado en el formulario llega como "": se guarda como NULL (importa en
        # numero_serie, que es unico: dos "" chocarian entre si).
        return valor.strip() or None if valor is not None else None


class EquipoOut(EquipoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    zona_id: Optional[int] = None
    created_at: datetime
    sucursal: Optional[SucursalMini] = None
    zona: Optional[ZonaMini] = None
    qr_activo: Optional[QrEquipoOut] = None
    # Cuenta de incidencias pendientes/en_proceso: es lo que define el color de salud del
    # equipo en el panel (verde/naranjo/rojo), ver frontend/src/utils/saludEquipo.js.
    incidencias_abiertas: int = 0
