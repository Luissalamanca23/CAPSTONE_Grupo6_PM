"""Puestos lado a lado de una misma maquina (ej. una polea doble).

La sesion de uso sigue siendo de la maquina (es lo que suma horas y dispara mantenciones);
los puestos solo dicen, en vivo, cuales se estan usando. La zona de la maquina se divide en
franjas verticales iguales, una por puesto, de izquierda a derecha.

Una persona ocupa la franja donde estan sus pies y, si el modelo es de pose, tambien las
franjas a las que llega con el brazo **extendido hacia el costado**: quien esta parado al
centro con un agarre en cada mano (un cruce de poleas) usa los dos puestos; quien trabaja con
un solo lado, solo ese. Una muneca cuenta solo si se aleja del centro de los hombros mas que
un ancho de hombros: con los brazos a los costados del cuerpo no alcanza, aunque la persona
este parada justo sobre la division.
"""

from __future__ import annotations

import numpy as np

from gymkeep_vision.zonas import Deteccion

HOMBROS = (5, 6)  # indices COCO
MUNECAS = (9, 10)
CONFIANZA_PUNTO = 0.3
EXTENSION = 1.0  # en anchos de hombros desde el centro del torso
ANCHO_MIN_HOMBROS = 0.22  # fraccion del alto de la persona


def franjas(poligono: np.ndarray, cantidad: int) -> list[tuple[float, float]]:
    """Rango x de cada puesto: el ancho de la zona dividido en partes iguales."""
    x1, x2 = float(poligono[:, 0].min()), float(poligono[:, 0].max())
    paso = (x2 - x1) / cantidad
    return [(x1 + i * paso, x1 + (i + 1) * paso) for i in range(cantidad)]


def _franja_de(x: float, rangos: list[tuple[float, float]]) -> int | None:
    for i, (a, b) in enumerate(rangos):
        if a <= x <= b:
            return i
    return None


def puestos_de(det: Deteccion, rangos: list[tuple[float, float]]) -> set[int]:
    """Puestos que usa una persona asignada a la maquina."""
    x_pies = (det.bbox[0] + det.bbox[2]) / 2
    usados = set()
    pies = _franja_de(x_pies, rangos)
    if pies is None:  # pies en el borde de la zona: el puesto mas cercano
        centros = [(a + b) / 2 for a, b in rangos]
        pies = int(np.argmin([abs(x_pies - c) for c in centros]))
    usados.add(pies)
    hombros = [det.puntos[i] for i in HOMBROS] if det.puntos is not None else []
    if len(hombros) == 2 and min(h[2] for h in hombros) >= CONFIANZA_PUNTO:
        centro = (hombros[0][0] + hombros[1][0]) / 2
        # De espaldas o de perfil los hombros salen juntos: el ancho minimo sale del alto de la
        # persona (los hombros miden ~22 %). Una mano en la cadera queda a ~13 % del centro y un
        # brazo extendido al costado, a mas de 40 %.
        ancho = max(abs(hombros[0][0] - hombros[1][0]), ANCHO_MIN_HOMBROS * (det.bbox[3] - det.bbox[1]))
        for i in MUNECAS:
            x, _, confianza = det.puntos[i]
            if confianza >= CONFIANZA_PUNTO and abs(x - centro) > EXTENSION * ancho:
                franja = _franja_de(x, rangos)
                if franja is not None:
                    usados.add(franja)
    return usados


def estado_puestos(
    nombres: list[str], poligono: np.ndarray, dets: list[Deteccion], activa: dict
) -> list[dict]:
    """Para el estado en vivo: cada puesto con si esta ocupado y cuantas personas lo usan.
    Una persona quieta (actividad False) no ocupa ningun puesto."""
    rangos = franjas(poligono, len(nombres))
    personas = [0] * len(nombres)
    for det in dets:
        if activa.get(id(det)) is False:
            continue
        for i in puestos_de(det, rangos):
            personas[i] += 1
    return [{"nombre": n, "ocupado": p > 0, "personas": p} for n, p in zip(nombres, personas)]
