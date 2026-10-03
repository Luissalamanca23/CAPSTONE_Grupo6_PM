"""Contratos de la integracion del modulo de vision con la plataforma (`/api/v1/vision`).

Las coordenadas de imagen (ROI de cada maquina y cajas de personas) van siempre
NORMALIZADAS entre 0 y 1 respecto del cuadro de la camara: asi no dependen de la
resolucion con que se muestre la imagen en el panel ni de la del video original.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Punto = tuple[float, float]
EstadoMaquinaVivo = Literal["libre", "candidata", "en_uso", "pausa"]


# ---------------------------------------------------------------- camaras y ROI


class RoiIn(BaseModel):
    """Poligono de la zona donde apoya los pies quien usa la maquina."""

    puntos: list[Punto] = Field(min_length=3, max_length=40, description="Vertices [x, y] entre 0 y 1.")

    @field_validator("puntos")
    @classmethod
    def _dentro_del_cuadro(cls, puntos: list[Punto]) -> list[Punto]:
        for x, y in puntos:
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("cada punto debe estar normalizado entre 0 y 1")
        return [(round(x, 5), round(y, 5)) for x, y in puntos]


class MaquinaEnCamara(BaseModel):
    equipo_id: int
    codigo_activo: str
    nombre: str
    categoria: Optional[str] = None
    estado: str = Field(description="Estado del equipo en el inventario (operativo, en_mantenimiento...).")
    roi: Optional[list[Punto]] = Field(default=None, description="Poligono normalizado; None si no tiene zona.")
    activo: bool = True


class ParametrosVision(BaseModel):
    """Reglas para decidir que hay uso (estudio §8.4.7). Se calibran POR CAMARA y viven en
    `camaras.configuracion["vision"]`; el pipeline las lee de aqui."""

    t_on_s: float = Field(30, gt=0, le=600, description="MP-45: presencia continua para abrir una sesion.")
    t_off_s: float = Field(90, gt=0, le=1800, description="MP-46: ausencia continua para cerrarla.")
    confianza_min: float = Field(0.50, ge=0.05, le=0.95, description="MP-47: confianza minima de una persona.")
    gracia_s: float = Field(2, ge=0, le=60, description="Huecos de deteccion que no cuentan como ausencia.")
    escala_tiempo: float = Field(1.0, gt=0, le=10, description="Segundos reales por segundo de video.")

    @model_validator(mode="after")
    def _t_off_mayor_que_gracia(self):
        if self.t_off_s <= self.gracia_s:
            raise ValueError("t_off_s debe ser mayor que gracia_s")
        return self


class CamaraVisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str
    sucursal_id: int
    zona_id: Optional[int] = None
    estado: str
    rtsp_url: Optional[str] = None
    ancho_px: Optional[int] = None
    alto_px: Optional[int] = None
    ultima_conexion: Optional[datetime] = None
    en_linea: bool = Field(description="El pipeline envio datos en los ultimos segundos.")
    tiene_cuadro: bool = Field(description="Hay una imagen de la camara para mostrar o dibujar zonas.")
    maquinas: int = Field(description="Maquinas con zona definida en esta camara.")


class CamaraVisionDetalle(CamaraVisionOut):
    parametros: ParametrosVision
    lista_maquinas: list[MaquinaEnCamara]


class ConfiguracionPipeline(BaseModel):
    """Lo que el pipeline de vision necesita para analizar una camara."""

    camara_id: int
    codigo: str
    nombre: str
    empresa_id: Optional[int] = None
    sucursal_id: int
    zona_id: Optional[int] = None
    parametros: ParametrosVision
    maquinas: list[MaquinaEnCamara] = Field(description="Solo maquinas activas y con zona definida.")


# ---------------------------------------------------------------- en vivo


class MaquinaVivo(BaseModel):
    equipo_id: int
    estado: EstadoMaquinaVivo
    sesion_s: Optional[float] = Field(default=None, ge=0, description="Duracion de la sesion en curso.")
    progreso_s: Optional[float] = Field(default=None, ge=0, description="Cuanto lleva hacia T_on o T_off.")
    umbral_s: Optional[float] = Field(default=None, ge=0, description="T_on o T_off, segun el estado.")
    personas: int = 0


class PersonaVivo(BaseModel):
    caja: tuple[float, float, float, float] = Field(description="x1, y1, x2, y2 normalizados.")
    confianza: float = Field(ge=0, le=1)
    track_id: Optional[int] = None
    equipo_id: Optional[int] = Field(default=None, description="Maquina a la que quedo asignada, si alguna.")


class ModeloVivo(BaseModel):
    nombre: str
    version: str


class EstadoVivoIn(BaseModel):
    """Lo que el pipeline envia cada ~1 s mientras analiza una camara."""

    timestamp: datetime = Field(description="Hora real del cuadro analizado.")
    ancho: int = Field(gt=0, description="Resolucion original del video.")
    alto: int = Field(gt=0)
    fps_analisis: Optional[float] = Field(default=None, ge=0)
    latencia_ms: Optional[float] = Field(default=None, ge=0, description="Tiempo de computo por cuadro.")
    modelo: ModeloVivo
    maquinas: list[MaquinaVivo] = []
    personas: list[PersonaVivo] = []


class EstadoVivoOut(BaseModel):
    camara_id: int
    en_linea: bool
    edad_s: Optional[float] = Field(default=None, description="Segundos desde el ultimo dato recibido.")
    timestamp: Optional[datetime] = None
    recibido: Optional[datetime] = None
    ancho: Optional[int] = None
    alto: Optional[int] = None
    fps_analisis: Optional[float] = None
    latencia_ms: Optional[float] = None
    maquinas: list[MaquinaVivo] = []
    personas: list[PersonaVivo] = []
    cuadro_timestamp: Optional[datetime] = None


# ---------------------------------------------------------------- uso de maquinas


class CamaraMini(BaseModel):
    id: int
    codigo: str
    nombre: str


class MaquinaUsoResumen(BaseModel):
    equipo_id: int
    codigo_activo: str
    nombre: str
    categoria: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    estado: str
    zona: Optional[str] = None
    horas_uso: float = Field(description="Horometro: union de intervalos de las sesiones cerradas.")
    horas_ultimos_7_dias: float
    sesiones: int
    ultima_sesion: Optional[datetime] = None
    ultima_mantencion: Optional[datetime] = None
    horas_desde_mantencion: Optional[float] = Field(
        default=None, description="Horas de uso desde la ultima mantencion (None si nunca tuvo una)."
    )
    incidencias_abiertas: int
    camaras: list[CamaraMini] = []
    medido_por_camara: bool = Field(description="Tiene al menos una camara con zona definida (uso medido).")
    en_uso_ahora: Optional[bool] = Field(
        default=None, description="Segun la camara en linea; None si ninguna camara la esta mirando ahora."
    )
    estado_vivo: Optional[MaquinaVivo] = None
    tiene_foto: bool


class UsoDiario(BaseModel):
    fecha: date
    horas: float
    sesiones: int


class SesionMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    duracion_segundos: Optional[int] = None
    estado: str
    origen: str
    confianza_promedio: Optional[float] = None
    camara_id: Optional[int] = None


class IncidenciaMini(BaseModel):
    id: int
    fecha_reporte: datetime
    tipo_falla: Optional[str] = None
    prioridad: str
    estado: str
    origen: str
    reportado_por: Optional[str] = None


class MantencionMini(BaseModel):
    id: int
    tipo: str
    tecnico: Optional[str] = None
    descripcion: str
    costo_total: Optional[float] = None
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None


class MaquinaUsoDetalle(BaseModel):
    resumen: MaquinaUsoResumen
    uso_diario: list[UsoDiario] = Field(description="Ultimos 30 dias, un registro por dia (incluye dias sin uso).")
    sesiones: list[SesionMini]
    incidencias: list[IncidenciaMini]
    mantenciones: list[MantencionMini]
