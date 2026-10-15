"""Puestos lado a lado de una maquina (polea doble): cual usa cada persona."""

import numpy as np

from gymkeep_vision.puestos import estado_puestos, franjas, puestos_de
from gymkeep_vision.zonas import Deteccion

# Polea doble: zona de 400 px de ancho, dos puestos de 200 px.
ZONA = np.array([[100, 500], [500, 500], [500, 600], [100, 600]], dtype=np.float32)
RANGOS = franjas(ZONA, 2)


def persona(x_pies, munecas=None, track_id=1):
    """munecas: (x izquierda, x derecha) o None para un modelo sin pose. Hombros de 60 px."""
    puntos = None
    if munecas is not None:
        puntos = [(0.0, 0.0, 0.0)] * 17
        puntos[5] = (x_pies - 30, 260.0, 0.9)
        puntos[6] = (x_pies + 30, 260.0, 0.9)
        puntos[9] = (munecas[0], 300.0, 0.9)
        puntos[10] = (munecas[1], 300.0, 0.9)
        puntos = tuple(puntos)
    return Deteccion(bbox=(x_pies - 40, 200, x_pies + 40, 580), confianza=0.9, track_id=track_id, puntos=puntos)


def test_franjas_iguales_de_izquierda_a_derecha():
    assert RANGOS == [(100.0, 300.0), (300.0, 500.0)]


def test_una_persona_en_un_lado_usa_un_solo_puesto():
    assert puestos_de(persona(180, munecas=(150, 220)), RANGOS) == {0}
    assert puestos_de(persona(420, munecas=(380, 460)), RANGOS) == {1}


def test_cruce_de_poleas_con_una_mano_en_cada_lado_usa_los_dos():
    assert puestos_de(persona(300, munecas=(140, 470)), RANGOS) == {0, 1}


def test_brazos_a_los_costados_sobre_la_division_no_usan_los_dos():
    # Parada justo sobre la division, con las manos junto al cuerpo (una a cada lado de la linea).
    assert len(puestos_de(persona(300, munecas=(270, 330)), RANGOS)) == 1


def test_sin_pose_cuenta_solo_donde_estan_los_pies():
    assert puestos_de(persona(180), RANGOS) == {0}


def test_munecas_poco_confiables_no_cuentan():
    det = persona(180, munecas=(150, 470))
    puntos = list(det.puntos)
    puntos[10] = (470.0, 300.0, 0.1)
    det = Deteccion(bbox=det.bbox, confianza=0.9, track_id=1, puntos=tuple(puntos))
    assert puestos_de(det, RANGOS) == {0}


def test_estado_en_vivo_por_puesto_y_la_persona_quieta_no_ocupa():
    usando = persona(180, munecas=(150, 220), track_id=1)
    quieta = persona(420, munecas=(400, 440), track_id=2)
    estado = estado_puestos(["Izquierda", "Derecha"], ZONA, [usando, quieta], {id(usando): True, id(quieta): False})
    assert estado == [
        {"nombre": "Izquierda", "ocupado": True, "personas": 1},
        {"nombre": "Derecha", "ocupado": False, "personas": 0},
    ]
