"""Decide si vale la pena correr YOLO en un cuadro: solo si algo cambio cerca de las maquinas.

En un equipo chico (Raspberry Pi) YOLO es casi todo el costo del pipeline, y la mayor parte
del tiempo la escena no cambia: el gimnasio vacio, o alguien sentado quieto. Comparar el
cuadro, en gris y achicado, con el del ultimo analisis cuesta menos de 1 ms. Si dentro de la
region de las maquinas cambio menos que `umbral` de los pixeles, se repiten las detecciones
anteriores en vez de correr YOLO.

Repetir es lo correcto en los dos casos: con la escena quieta sigue la misma gente en el
mismo lugar (la presencia se mantiene) y, como sus puntos del cuerpo no cambian, la medicion
de actividad la ve quieta. Igual se corre YOLO al menos cada `max_sin_analisis_s`, para
corregir lo que un cambio muy lento pudiera esconder.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

ANCHO_COMPARACION = 160  # px: suficiente para ver a una persona moverse, casi gratis


@dataclass(frozen=True)
class ParametrosMovimiento:
    umbral: float = 0.003  # fraccion de pixeles de la region que tiene que cambiar
    diferencia_min: int = 18  # cambio de gris (0-255) para contar un pixel como cambiado
    max_sin_analisis_s: float = 3.0


class DetectorMovimiento:
    def __init__(self, parametros: ParametrosMovimiento | None = None):
        self.p = parametros or ParametrosMovimiento()
        self._mascara: np.ndarray | None = None
        self._referencia: np.ndarray | None = None
        self._t_ultimo_analisis = float("-inf")
        self.analizados = 0
        self.omitidos = 0

    def preparar(self, poligonos: list[np.ndarray], ancho: int, alto: int) -> None:
        """Region de interes: las zonas de las maquinas ampliadas hacia arriba, porque la zona
        marca donde se apoyan los pies y el cuerpo de quien la usa queda encima."""
        escala = ANCHO_COMPARACION / ancho
        tam = (ANCHO_COMPARACION, max(1, round(alto * escala)))
        mascara = np.zeros((tam[1], tam[0]), np.uint8)
        for poligono in poligonos:
            p = np.asarray(poligono, dtype=np.float32) * escala
            x1, y1 = p.min(axis=0)
            x2, y2 = p.max(axis=0)
            alto_zona = max(y2 - y1, 1.0)
            # Una persona de pie mide unas 3-4 veces la profundidad de la zona de sus pies.
            caja = np.array([[x1, y1 - 4 * alto_zona], [x2, y1 - 4 * alto_zona], [x2, y2], [x1, y2]])
            cv2.fillPoly(mascara, [np.round(caja).astype(np.int32)], 1)
        self._mascara = mascara.astype(bool)
        self._referencia = None

    def hay_que_analizar(self, t: float, cuadro: np.ndarray) -> bool:
        gris = cv2.cvtColor(
            cv2.resize(cuadro, self._mascara.shape[::-1], interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY
        )
        gris = cv2.GaussianBlur(gris, (5, 5), 0)
        analizar = (
            self._referencia is None
            or t - self._t_ultimo_analisis >= self.p.max_sin_analisis_s
            or self._cambio(gris) >= self.p.umbral
        )
        if analizar:
            self._referencia = gris
            self._t_ultimo_analisis = t
            self.analizados += 1
        else:
            self.omitidos += 1
        return analizar

    def _cambio(self, gris: np.ndarray) -> float:
        diferencia = cv2.absdiff(gris, self._referencia)[self._mascara]
        if diferencia.size == 0:
            return 1.0
        return float((diferencia >= self.p.diferencia_min).mean())
