from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.gymkeep import OrigenUso


class SesionUsoOut(BaseModel):
    """Uso consolidado de un equipo (inicio, fin, duracion). Lo genera el modulo de vision
    a partir de sus eventos inicio_uso / fin_uso; no guarda cada cuadro de video."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    camara_id: Optional[int] = None
    modelo_ia_id: Optional[int] = None
    origen: OrigenUso
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    duracion_segundos: Optional[int] = None
    confianza_promedio: Optional[float] = None
    cantidad_eventos: int
    estado: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_json")


class HorometroEquipoOut(BaseModel):
    """Horas de uso acumuladas de un equipo (horometro virtual, §6.6.4 del estudio)."""

    equipo_id: int
    codigo_activo: str
    nombre: str
    sesiones_cerradas: int
    # Union de los intervalos de las sesiones: tiempo con la maquina ocupada. Dos sesiones
    # solapadas (dos camaras, dos personas) cuentan una sola vez.
    horas_uso: float
    # Suma simple de duraciones. Si difiere de horas_uso, hay doble contabilidad (§6.6.3).
    horas_suma: float
    ultima_sesion: Optional[datetime] = None
