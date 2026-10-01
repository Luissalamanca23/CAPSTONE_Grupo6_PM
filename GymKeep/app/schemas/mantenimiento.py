from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EquipoMiniMant(BaseModel):
    """Referencia minima al equipo, para poder mostrar el historial de mantenimientos sin
    equipo_id (vista de Costos) sin tener que pedir cada equipo por separado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    codigo_activo: str
    categoria: Optional[str] = None


class MantenimientoCreate(BaseModel):
    """Registro de un mantenimiento que un tecnico ya realizo (correctivo o preventivo).

    Si se indican `incidencia_ids`, ese mantenimiento las deja resueltas: la tabla
    `mantenimientos` liga cada fila a UNA incidencia (no a varias), asi que el CRUD crea un
    registro por cada incidencia elegida, todos con los mismos datos de tecnico/descripcion.
    Si no se indica ninguna (ej. mantenimiento preventivo sin falla asociada), queda un unico
    registro general del equipo.
    """

    equipo_id: int
    tipo: Literal["correctivo", "preventivo"] = "correctivo"
    tecnico: str = Field(min_length=1, description="Quien realizo el mantenimiento.")
    descripcion: str = Field(min_length=1, description="Que se hizo o que se reviso.")
    incidencia_ids: List[int] = Field(
        default_factory=list,
        description="Incidencias abiertas del equipo que este mantenimiento deja resueltas.",
    )
    costo_total: Optional[float] = Field(
        default=None, ge=0, description="Costo total de este mantenimiento (repuestos + mano de obra), si aplica."
    )


class MantenimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    incidencia_id: Optional[int] = None
    tipo: str
    tecnico: Optional[str] = None
    descripcion: str
    costo_total: Optional[float] = None
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    equipo: Optional[EquipoMiniMant] = None
