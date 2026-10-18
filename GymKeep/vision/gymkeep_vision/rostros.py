"""Detector de rostros para la privacidad de la imagen (YuNet de OpenCV).

El difuminado de cabezas depende de que YOLO detecte a la persona: alguien muy cerca de la
camara o cortado por el borde puede quedar sin detectar y con la cara visible. Este detector
busca rostros en todo el cuadro, sin depender de YOLO, para difuminarlos tambien.

El modelo (~230 KB) vive en vision/modelos/ y se descarga la primera vez. Si no se puede
cargar, el pipeline sigue funcionando solo con el difuminado de cabezas y lo avisa en el log.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from gymkeep_vision.config import RAIZ

log = logging.getLogger(__name__)

MODELO = "face_detection_yunet_2023mar.onnx"
URL = f"https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/{MODELO}"
ANCHO_MIN = 640  # imagenes mas chicas (CCTV 352x240) se agrandan para encontrar caras pequenas
ANCHO_MAX = 1280
UMBRAL = 0.6  # bajo a proposito: es mejor difuminar de mas que dejar una cara visible
MARGEN = 0.25  # se amplia cada caja para cubrir pelo y orejas


def ruta_modelo() -> Path:
    return RAIZ / "modelos" / MODELO


def descargar(ruta: Path | None = None) -> Path:
    ruta = ruta or ruta_modelo()
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        log.info("Descargando el detector de rostros en %s", ruta)
        temporal = ruta.with_suffix(".part")
        urllib.request.urlretrieve(URL, temporal)
        temporal.replace(ruta)
    return ruta


class DetectorRostros:
    def __init__(self, ruta: Path | None = None, umbral: float = UMBRAL):
        self._red = cv2.FaceDetectorYN.create(str(descargar(ruta)), "", (320, 320), umbral, 0.3, 5000)

    def detectar(self, img: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Cajas (x1, y1, x2, y2) en coordenadas de `img`, ya ampliadas con el margen."""
        alto, ancho = img.shape[:2]
        escala = ANCHO_MIN / ancho if ancho < ANCHO_MIN else min(1.0, ANCHO_MAX / ancho)
        entrada = img if escala == 1.0 else cv2.resize(img, (round(ancho * escala), round(alto * escala)))
        self._red.setInputSize((entrada.shape[1], entrada.shape[0]))
        _, caras = self._red.detect(entrada)
        cajas = []
        for x, y, w, h in ([] if caras is None else caras[:, :4]):
            x, y, w, h = x / escala, y / escala, w / escala, h / escala
            mx, my = w * MARGEN, h * MARGEN
            cajas.append(
                (
                    max(0, int(x - mx)),
                    max(0, int(y - my)),
                    min(ancho, int(x + w + mx)),
                    min(alto, int(y + h + my)),
                )
            )
        return cajas


def crear() -> DetectorRostros | None:
    """Detector listo, o None si el modelo no se pudo descargar o cargar."""
    try:
        return DetectorRostros()
    except Exception as e:  # sin red, OpenCV antiguo, archivo corrupto...
        log.warning("Sin detector de rostros (%s): solo se difuminan las cabezas detectadas por YOLO", e)
        return None
