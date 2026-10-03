from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.gymkeep import EstadoEquipo, EstadoIncidencia, OrigenIncidencia, PrioridadIncidencia


class TipoFallaOut(BaseModel):
    """Fila del catalogo administrable `tipos_falla` (reemplaza el antiguo enum fijo)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    categoria: str
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
    elige categoria + tipo de falla, marca que tan grave es y si la maquina sigue
    funcionando, y escribe su nombre (unico campo de texto libre). La prioridad final se
    deriva de `gravedad` y `funcional`, no solo de la prioridad_base del catalogo."""

    token: str = Field(description="Token UUID del QR activo del equipo (viene en la URL escaneada).")
    tipo_falla_codigo: str
    gravedad: Literal["leve", "grave"] = Field(
        description="Que tan grave le parecio la falla a quien reporta: leve -> prioridad baja, grave -> alta."
    )
    funcional: bool = Field(
        default=True,
        description="Si la maquina sigue pudiendo usarse. En False: prioridad urgente y el "
        "equipo pasa a estado 'fuera_de_servicio' automaticamente.",
    )
    reportado_por: str = Field(min_length=1, description="Nombre de quien reporta; unico campo de texto libre.")
    descripcion: Optional[str] = Field(
        default=None,
        description="Texto libre opcional. Solo lo pide el formulario cuando la categoria elegida es "
        "'otro' (no hay un tipo de falla especifico que elegir, asi que se le pide describirlo).",
    )


class IncidenciaUpdate(BaseModel):
    estado: Optional[EstadoIncidencia] = None
    prioridad: Optional[PrioridadIncidencia] = None


class EquipoMiniIncidencia(BaseModel):
    """Datos minimos del equipo para mostrar en el listado de incidencias sin tener que
    pedir el equipo aparte: nombre (hoy el panel solo mostraba el id) y lo necesario para
    pintar el color de salud de la maquina (ver saludEquipo.js)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    estado: EstadoEquipo
    incidencias_abiertas: int


class IncidenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipo_id: int
    equipo: Optional[EquipoMiniIncidencia] = None
    tipo_falla: TipoFallaOut
    origen: OrigenIncidencia
    descripcion: Optional[str] = None
    reportado_por: Optional[str] = None
    estado: EstadoIncidencia
    prioridad: PrioridadIncidencia
    fecha_reporte: datetime
    fecha_resolucion: Optional[datetime] = None
