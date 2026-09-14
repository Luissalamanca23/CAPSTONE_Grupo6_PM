from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.incidencia import EstadoIncidencia, PrioridadIncidencia, TipoFalla


class IncidenciaCreate(BaseModel):
    """Creacion manual (panel de tecnicos): permite indicar equipo, tipo de falla y,
    opcionalmente, descripcion/prioridad. Si no se indican, se autocompletan."""

    equipo_id: int
    tipo_falla: TipoFalla
    descripcion: Optional[str] = None
    reportado_por: Optional[str] = None
    prioridad: Optional[PrioridadIncidencia] = None


class IncidenciaCreateByQR(BaseModel):
    """Encuesta del Portal de Reporte Express: el cliente solo elige el tipo de falla y
    escribe su nombre. La prioridad se calcula sola segun el tipo de falla."""

    codigo_qr: str
    tipo_falla: TipoFalla
    reportado_por: str = Field(min_length=1, description="Nombre de quien reporta; unico campo de texto libre.")


class IncidenciaUpdate(BaseModel):
    estado: Optional[EstadoIncidencia] = None
    prioridad: Optional[PrioridadIncidencia] = None


class IncidenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    tipo_falla: TipoFalla
    descripcion: Optional[str] = None
    reportado_por: Optional[str] = None
    estado: EstadoIncidencia
    prioridad: PrioridadIncidencia
    fecha_reporte: datetime
    fecha_resolucion: Optional[datetime] = None


class TipoFallaOut(BaseModel):
    valor: TipoFalla
    etiqueta: str
