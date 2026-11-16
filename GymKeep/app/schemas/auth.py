from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.auth import clave_valida, normalizar_run

MENSAJE_CLAVE = "La clave debe tener solo numeros, de 4 a 8 digitos."


def _run(valor: str) -> str:
    run = normalizar_run(valor)
    if run is None:
        raise ValueError("El RUN no es valido (revisa el digito verificador).")
    return run


def _clave(valor: str) -> str:
    if not clave_valida(valor):
        raise ValueError(MENSAJE_CLAVE)
    return valor


class LoginIn(BaseModel):
    # Sin validar el formato aqui: un RUN/clave mal escritos responden lo mismo que uno incorrecto.
    run: str = Field(max_length=20)
    clave: str = Field(max_length=32)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run: str
    nombre: str
    rol: Literal["admin", "tecnico"]
    activo: bool
    ultimo_acceso: Optional[datetime] = None
    creado_en: Optional[datetime] = None


class EstadoAuthOut(BaseModel):
    """Para la pantalla de login: si todavia no hay ningun usuario hay que crear el primero."""

    hay_usuarios: bool


class UsuarioCreate(BaseModel):
    run: str
    nombre: str = Field(min_length=2, max_length=120)
    rol: Literal["admin", "tecnico"] = "tecnico"
    clave: str

    @field_validator("run")
    @classmethod
    def _v_run(cls, v: str) -> str:
        return _run(v)

    @field_validator("clave")
    @classmethod
    def _v_clave(cls, v: str) -> str:
        return _clave(v)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        return v.strip()


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=120)
    rol: Optional[Literal["admin", "tecnico"]] = None
    activo: Optional[bool] = None
    # Restablecer la clave de otra persona (solo administrador).
    clave: Optional[str] = None

    @field_validator("clave")
    @classmethod
    def _v_clave(cls, v):
        return None if v is None else _clave(v)


class CambiarClaveIn(BaseModel):
    clave_actual: str = Field(max_length=32)
    clave_nueva: str

    @field_validator("clave_nueva")
    @classmethod
    def _v_nueva(cls, v: str) -> str:
        return _clave(v)
