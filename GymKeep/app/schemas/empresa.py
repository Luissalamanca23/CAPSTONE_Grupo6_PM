from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.gymkeep import EstadoEmpresa


class EmpresaBase(BaseModel):
    razon_social: str
    rut: Optional[str] = None
    nombre_fantasia: Optional[str] = None
    email_contacto: Optional[str] = None
    telefono: Optional[str] = None


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaOut(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoEmpresa
    created_at: datetime
