from typing import Optional

from pydantic import BaseModel, Field


class InformeFila(BaseModel):
    """Una fila del informe tal como la dejo la persona en pantalla."""

    fecha: str = Field("", max_length=60)
    codigo: str = Field("", max_length=64)
    maquina: str = Field("", max_length=160)
    incidencias: str = Field("", max_length=2000)
    mantenimientos: str = Field("", max_length=2000)
    observaciones: str = Field("", max_length=2000)
    estado: str = Field("", max_length=80)


class InformeExcelIn(BaseModel):
    gimnasio: str = Field(..., min_length=1, max_length=200)
    responsable: str = Field("", max_length=150)
    etiqueta: str = Field("", max_length=80)
    desde: str = Field("", max_length=12)
    hasta: str = Field("", max_length=12)
    generado: str = Field("", max_length=12)
    filas: list[InformeFila] = Field(default_factory=list, max_length=3000)
    nombre_archivo: Optional[str] = Field(None, max_length=80)
