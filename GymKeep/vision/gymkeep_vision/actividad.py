"""Actividad de cada persona a partir de su pose: distingue usar una maquina de solo estar
encima de ella (sentado mirando el celular, conversando, esperando).

Con un modelo de pose (yolo26n-pose) cada deteccion trae 17 puntos del cuerpo. Una persona
que hace un ejercicio mueve brazos o piernas de forma sostenida; una que descansa los deja
quietos. La actividad es la mayor desviacion estandar, en una ventana de pocos segundos, de
la posicion de codos, munecas, rodillas y tobillos, medida en alturas de su caja (asi no
depende de la distancia a la camara).

Medido sobre videos de gimnasio a 5 analisis/s con ventana de 4 s: sentado o de pie quieto
da 0.01-0.06; un ejercicio (press, remo, peso muerto, sentadilla) da 0.12-0.75. El umbral
por defecto (0.08) queda entre ambos.

Una persona sin track_id o sin puntos (modelo sin pose) queda como `None`: actividad
desconocida, y el monitor la trata como activa (el comportamiento de siempre).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from gymkeep_vision.zonas import Deteccion

# Indices COCO de codos, munecas, rodillas y tobillos: lo que se mueve al hacer un ejercicio.
ARTICULACIONES = (7, 8, 9, 10, 13, 14, 15, 16)


@dataclass(frozen=True)
class ParametrosActividad:
    ventana_s: float = 4.0  # cuanto movimiento hacia atras se mira
    umbral: float = 0.08  # desviacion minima (en alturas de la caja) para contar como activa
    # Una persona activa sigue contando como activa este tiempo despues de quedarse quieta:
    # cubre el punto muerto entre una repeticion y la siguiente.
    retencion_s: float = 2.0
    confianza_punto: float = 0.3  # puntos menos confiables que esto no se usan
    muestras_min: int = 5  # con menos muestras en la ventana no se decide (persona recien vista)
    olvido_s: float = 10.0  # se descarta el historial de quien no aparece hace mas que esto


class MedidorActividad:
    """Lleva el historial de pose por track_id y dice quien esta activo en cada instante."""

    def __init__(self, parametros: ParametrosActividad | None = None):
        self.p = parametros or ParametrosActividad()
        self._historial: dict[int, deque] = {}
        self._ultima_actividad: dict[int, float] = {}
        self._visto: dict[int, float] = {}

    def actualizar(self, t: float, detecciones: list[Deteccion]) -> dict[int, bool | None]:
        """Registra las poses del instante `t` y devuelve, por id() de cada deteccion, si la
        persona esta activa (True/False) o si no se puede saber (None)."""
        resultado: dict[int, bool | None] = {}
        for det in detecciones:
            if det.track_id is None or det.puntos is None:
                resultado[id(det)] = None
                continue
            resultado[id(det)] = self._medir(t, det)
        self._olvidar(t)
        return resultado

    def _medir(self, t: float, det: Deteccion) -> bool | None:
        tid = det.track_id
        alto = max(1.0, det.bbox[3] - det.bbox[1])
        puntos = np.asarray(det.puntos, dtype=np.float32)[list(ARTICULACIONES)]
        historial = self._historial.setdefault(tid, deque())
        historial.append((t, puntos[:, :2] / alto, puntos[:, 2]))
        while historial and t - historial[0][0] > self.p.ventana_s:
            historial.popleft()
        self._visto[tid] = t

        actividad = self.actividad(tid)
        if actividad is None:
            return None
        if actividad >= self.p.umbral:
            self._ultima_actividad[tid] = t
            return True
        return t - self._ultima_actividad.get(tid, float("-inf")) <= self.p.retencion_s

    def actividad(self, track_id: int) -> float | None:
        """Mayor desviacion de las articulaciones confiables en la ventana, o None si todavia
        no hay muestras suficientes."""
        historial = self._historial.get(track_id)
        if not historial or len(historial) < self.p.muestras_min:
            return None
        posiciones = np.stack([h[1] for h in historial])  # (n, articulaciones, 2)
        confianzas = np.stack([h[2] for h in historial])  # (n, articulaciones)
        confiables = confianzas.mean(axis=0) >= self.p.confianza_punto
        if not confiables.any():
            return None
        desviacion = posiciones.std(axis=0).mean(axis=1)  # por articulacion
        return float(desviacion[confiables].max())

    def _olvidar(self, t: float) -> None:
        for tid in [tid for tid, visto in self._visto.items() if t - visto > self.p.olvido_s]:
            self._historial.pop(tid, None)
            self._ultima_actividad.pop(tid, None)
            self._visto.pop(tid, None)
