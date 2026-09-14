from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.gymkeep import EstadoIncidencia, OrigenIncidencia, PrioridadIncidencia


class TipoFallaOut(BaseModel):
    """Fila del catalogo administrable `tipos_falla` (reemplaza el antiguo enum fijo)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    prioridad_base: PrioridadIncidencia
    permite_reporte_qr: bool
    permite_deteccion_ia: bool


class IncidenciaCreate(BaseModel):
    """Creacion manual (panel de tecnicos): permite indicar equipo y tipo de falla (por su
    codigo de catalogo) y, opcionalmente, descripcion/prioridad. Si no se indican, se
    autocompletan a partir de la prioridad_base del tipo de falla."""

    equipo_id: int
    tipo_falla_codigo: str
    descripcion: Optional[str] = None
    reportado_por: Optional[str] = None
    prioridad: Optional[PrioridadIncidencia] = None
    origen: OrigenIncidencia = OrigenIncidencia.tecnico


class IncidenciaCreateByQR(BaseModel):
    """Encuesta del Portal de Reporte Express: el cliente escanea el QR (token del equipo),
    elige el tipo de falla en la encuesta y escribe su nombre (unico campo de texto libre).
    La prioridad se calcula sola segun la prioridad_base del tipo de falla."""

    token: str = Field(description="Token UUID del QR activo del equipo (viene en la URL escaneada).")
    tipo_falla_codigo: str
    reportado_por: str = Field(min_length=1, description="Nombre de quien reporta; unico campo de texto libre.")


class IncidenciaUpdate(BaseModel):
    estado: Optional[EstadoIncidencia] = None
    prioridad: Optional[PrioridadIncidencia] = None


class IncidenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    tipo_falla: TipoFallaOut
    origen: OrigenIncidencia
    descripcion: Optional[str] = None
    reportado_por: Optional[str] = None
    estado: EstadoIncidencia
    prioridad: PrioridadIncidencia
    fecha_reporte: datetime
    fecha_resolucion: Optional[datetime] = None
