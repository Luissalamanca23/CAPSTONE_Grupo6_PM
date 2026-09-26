"""Configuracion de una camara: que maquinas ve, donde estan (ROI) y con que parametros
se decide que hay uso. Se carga desde un YAML (ver config/ejemplo_camara.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from gymkeep_vision.sesiones import ParametrosUso

RAIZ = Path(__file__).resolve().parents[1]  # GymKeep/vision/


@dataclass
class ConfigCamara:
    codigo: str
    nombre: str | None = None
    id: int | None = None  # camaras.id en GymKeep (se resuelve por codigo si falta)
    sucursal_codigo: str | None = None
    zona_nombre: str | None = None
    empresa_id: int | None = None
    sucursal_id: int | None = None
    zona_id: int | None = None


@dataclass
class ConfigModelo:
    pesos: str = "yolo26n.pt"  # liviano: corre en CPU
    nombre: str = "gymkeep-usage-detector"
    version: str = "0.1.0"
    id: int | None = None  # modelos_ia.id en GymKeep (opcional)
    tracker: str = "bytetrack.yaml"
    imgsz: int = 640
    dispositivo: str | None = None  # None = automatico (GPU si hay)
    # Confianza que se le pide al detector. Es mas baja que confianza_min a proposito:
    # ByteTrack usa las detecciones debiles para no perder a una persona tapada por la
    # maquina. La presencia en la ROI se decide despues con confianza_min (MP-47).
    confianza_detector: float = 0.10

    def ruta_pesos(self) -> str:
        ruta = Path(self.pesos)
        if ruta.is_absolute() or ruta.exists():
            return str(ruta)
        # Nombre simple (ej. yolo26n.pt): vive en vision/modelos/ y Ultralytics lo
        # descarga ahi la primera vez.
        return str(RAIZ / "modelos" / ruta.name)


@dataclass
class ConfigMaquina:
    nombre: str
    codigo_activo: str
    roi: list[list[float]]
    equipo_id: int | None = None  # equipos.id en GymKeep (se resuelve por codigo_activo)
    categoria: str | None = None
    criterio: str | None = None  # si falta, usa criterio_zona global


@dataclass
class Config:
    camara: ConfigCamara
    maquinas: list[ConfigMaquina]
    modelo: ConfigModelo = field(default_factory=ConfigModelo)
    uso: ParametrosUso = field(default_factory=ParametrosUso)
    confianza_min: float = 0.50  # MP-47
    intervalo_analisis_s: float = 0.2  # 5 analisis por segundo bastan para medir uso
    criterio_zona: str = "pie"
    solape_min: float = 0.3
    resolucion_referencia: tuple[int, int] | None = None  # (ancho, alto) en que se dibujaron las ROI
    # Segundos reales por cada segundo de video. Es 1.0 en una camara en vivo, pero un video
    # exportado desde un grabador (NVR/DVR) puede venir acelerado: el archivo dice 25 fps y la
    # camara grabo a menos. Se calibra con el reloj impreso en la imagen:
    # (hora final - hora inicial) / duracion del archivo.
    escala_tiempo: float = 1.0
    difuminar_personas: bool = True  # privacidad: difumina cabezas en video y evidencias
    ruta: Path | None = None

    def con_parametros(self, **cambios) -> "Config":
        """Copia con parametros de uso cambiados (ej. desde la linea de comandos)."""
        uso = {k: v for k, v in cambios.items() if k in ParametrosUso.__dataclass_fields__ and v is not None}
        resto = {k: v for k, v in cambios.items() if k not in uso and v is not None}
        return replace(self, uso=replace(self.uso, **uso), **resto)


def _roi_a_poligono(roi) -> list[list[float]]:
    # Mismo formato rectangular que usa camara_equipos.roi en seed.sql, o una lista de puntos.
    if isinstance(roi, dict):
        x, y, w, h = (float(roi[k]) for k in ("x", "y", "w", "h"))
        return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    return [[float(px), float(py)] for px, py in roi]


def cargar(ruta: str | Path) -> Config:
    ruta = Path(ruta)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

    parametros = datos.get("parametros", {})
    uso_campos = ParametrosUso.__dataclass_fields__
    uso = ParametrosUso(**{k: v for k, v in parametros.items() if k in uso_campos})

    maquinas = [
        ConfigMaquina(
            nombre=m["nombre"],
            codigo_activo=m["codigo_activo"],
            roi=_roi_a_poligono(m["roi"]),
            equipo_id=m.get("equipo_id"),
            categoria=m.get("categoria"),
            criterio=m.get("criterio"),
        )
        for m in datos.get("maquinas", [])
    ]
    if not maquinas:
        raise ValueError(f"{ruta}: no hay maquinas definidas")
    nombres = [m.nombre for m in maquinas]
    if len(set(nombres)) != len(nombres):
        raise ValueError(f"{ruta}: hay nombres de maquina repetidos")

    resolucion = datos.get("resolucion_referencia")
    return Config(
        camara=ConfigCamara(**datos["camara"]),
        maquinas=maquinas,
        modelo=ConfigModelo(**datos.get("modelo", {})),
        uso=uso,
        confianza_min=parametros.get("confianza_min", 0.50),
        intervalo_analisis_s=parametros.get("intervalo_analisis_s", 0.2),
        criterio_zona=parametros.get("criterio_zona", "pie"),
        solape_min=parametros.get("solape_min", 0.3),
        resolucion_referencia=tuple(resolucion) if resolucion else None,
        escala_tiempo=datos.get("escala_tiempo", 1.0),
        difuminar_personas=datos.get("privacidad", {}).get("difuminar_personas", True),
        ruta=ruta,
    )
