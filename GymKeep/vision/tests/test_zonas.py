from pathlib import Path

import pytest

from gymkeep_vision.config import cargar
from gymkeep_vision.zonas import Deteccion, ZonaMaquina, asignar

CINTA = [[100, 100], [300, 100], [300, 400], [100, 400]]
BICI = [[300, 100], [500, 100], [500, 400], [300, 400]]


def preparar(*zonas):
    for z in zonas:
        z.preparar(600, 800)
    return list(zonas)


def test_persona_se_asigna_por_su_punto_de_apoyo():
    zonas = preparar(ZonaMaquina("cinta", CINTA), ZonaMaquina("bici", BICI))
    sobre_cinta = Deteccion((150, 50, 250, 350), 0.9, 1)  # pie en (200, 350)
    fuera = Deteccion((600, 50, 700, 350), 0.9, 2)
    resultado = asignar([sobre_cinta, fuera], zonas)
    assert resultado["cinta"] == [sobre_cinta]
    assert resultado["bici"] == []


def test_persona_entre_dos_roi_superpuestas_va_solo_a_una():
    # Las ROI se superponen en la franja x=280..320 (maquinas pegadas en la imagen).
    cinta = [[100, 100], [320, 100], [320, 400], [100, 400]]
    bici = [[280, 100], [500, 100], [500, 400], [280, 400]]
    zonas = preparar(ZonaMaquina("cinta", cinta), ZonaMaquina("bici", bici))
    # Pie en x=315 (dentro de ambas), pero la caja cae entera sobre la bici.
    det = Deteccion((285, 50, 345, 350), 0.9, 1)
    assert all(z.acepta(det) for z in zonas)
    resultado = asignar([det], zonas)
    assert resultado["bici"] == [det]
    assert resultado["cinta"] == []


def test_criterio_solape():
    zona = preparar(ZonaMaquina("prensa", CINTA, criterio="solape", solape_min=0.5))[0]
    assert zona.acepta(Deteccion((120, 120, 280, 380), 0.9))  # caja completa dentro
    assert not zona.acepta(Deteccion((250, 120, 450, 380), 0.9))  # solo 25 % dentro


def test_escalar_roi_a_otra_resolucion():
    zona = ZonaMaquina("cinta", CINTA)
    zona.escalar(0.5, 0.5)
    zona.preparar(300, 400)
    assert zona.contiene(100, 150)
    assert not zona.contiene(200, 150)


def test_criterio_invalido():
    with pytest.raises(ValueError):
        ZonaMaquina("x", CINTA, criterio="magia")


@pytest.mark.parametrize("ruta", sorted((Path(__file__).resolve().parents[1] / "config").glob("*.yaml")), ids=lambda p: p.name)
def test_configs_de_ejemplo_son_validas(ruta):
    cfg = cargar(ruta)
    assert cfg.uso.t_off_s > cfg.uso.t_on_s
    assert all(len(m.roi) >= 3 for m in cfg.maquinas)
    assert len({m.codigo_activo for m in cfg.maquinas}) == len(cfg.maquinas)
