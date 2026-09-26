"""Regiones de interes (ROI) por maquina y asignacion de personas a maquinas.

Cada maquina se describe con un poligono en coordenadas de imagen (equivalente a
`camara_equipos.roi` del esquema). Una persona detectada se asigna **como maximo a una
maquina**: si su punto de apoyo cae dentro de dos ROI que se tocan, gana la que cubre mas
area de su caja. Asi una misma persona no suma uso a dos maquinas vecinas (§6.6.3).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

CRITERIOS = ("pie", "centro", "solape")


@dataclass(frozen=True)
class Deteccion:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 en pixeles
    confianza: float
    track_id: int | None = None

    def ancla(self, criterio: str) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        if criterio == "centro":
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        # 'pie' (y tambien 'solape' para desempatar): centro del borde inferior, que es
        # donde la persona se apoya sobre la maquina o el piso.
        return ((x1 + x2) / 2, y2)


class ZonaMaquina:
    def __init__(
        self,
        nombre: str,
        poligono: list[list[float]],
        *,
        criterio: str = "pie",
        solape_min: float = 0.3,
    ):
        if criterio not in CRITERIOS:
            raise ValueError(f"criterio '{criterio}' invalido; usar uno de {CRITERIOS}")
        if len(poligono) < 3:
            raise ValueError(f"la ROI de '{nombre}' necesita al menos 3 puntos")
        self.nombre = nombre
        self.poligono = np.asarray(poligono, dtype=np.float32)
        self.criterio = criterio
        self.solape_min = solape_min
        self._mascara: np.ndarray | None = None

    def escalar(self, fx: float, fy: float) -> None:
        """Adapta la ROI si el video no tiene la resolucion con que se dibujo."""
        self.poligono = self.poligono * np.array([fx, fy], dtype=np.float32)
        self._mascara = None

    def preparar(self, alto: int, ancho: int) -> None:
        mascara = np.zeros((alto, ancho), dtype=np.uint8)
        cv2.fillPoly(mascara, [self.poligono.round().astype(np.int32)], 1)
        self._mascara = mascara

    def contiene(self, x: float, y: float) -> bool:
        return cv2.pointPolygonTest(self.poligono, (float(x), float(y)), False) >= 0

    def solape(self, bbox: tuple[float, float, float, float]) -> float:
        """Fraccion del area de la caja que cae dentro de la ROI (0..1)."""
        if self._mascara is None:
            raise RuntimeError("llamar preparar() antes de medir solape")
        alto, ancho = self._mascara.shape
        x1, y1, x2, y2 = (int(round(v)) for v in bbox)
        x1, x2 = max(0, x1), min(ancho, x2)
        y1, y2 = max(0, y1), min(alto, y2)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        return float(self._mascara[y1:y2, x1:x2].mean())

    def acepta(self, det: Deteccion) -> bool:
        if self.criterio == "solape":
            return self.solape(det.bbox) >= self.solape_min
        return self.contiene(*det.ancla(self.criterio))


def asignar(detecciones: list[Deteccion], zonas: list[ZonaMaquina]) -> dict[str, list[Deteccion]]:
    """Reparte las detecciones entre las maquinas. Cada deteccion va a una sola maquina."""
    asignadas: dict[str, list[Deteccion]] = {z.nombre: [] for z in zonas}
    for det in detecciones:
        candidatas = [z for z in zonas if z.acepta(det)]
        if not candidatas:
            continue
        mejor = max(candidatas, key=lambda z: z.solape(det.bbox)) if len(candidatas) > 1 else candidatas[0]
        asignadas[mejor.nombre].append(det)
    return asignadas
