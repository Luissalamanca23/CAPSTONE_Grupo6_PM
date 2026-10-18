"""Saltar YOLO cuando nada cambia cerca de las maquinas (equipos chicos como una Raspberry Pi)."""

import numpy as np

from gymkeep_vision.__main__ import main as _main  # noqa: F401 (asegura que el modulo carga)
from gymkeep_vision.movimiento import DetectorMovimiento, ParametrosMovimiento

ZONA = np.array([[600, 500], [800, 500], [800, 600], [600, 600]], dtype=np.float32)


def detector(**kw):
    d = DetectorMovimiento(ParametrosMovimiento(**kw))
    d.preparar([ZONA], 1280, 720)
    return d


def escena(persona_x=None):
    img = np.full((720, 1280, 3), 60, np.uint8)
    if persona_x is not None:
        img[250:600, persona_x : persona_x + 80] = 220  # una persona sobre la maquina
    return img


def test_escena_quieta_no_se_analiza_y_un_movimiento_cerca_de_la_maquina_si():
    d = detector()
    assert d.hay_que_analizar(0.0, escena(650)) is True  # primer cuadro: siempre
    assert d.hay_que_analizar(0.4, escena(650)) is False  # nada cambio
    assert d.hay_que_analizar(0.8, escena(690)) is True  # la persona se movio


def test_movimiento_lejos_de_las_maquinas_no_despierta_a_yolo():
    d = detector()
    d.hay_que_analizar(0.0, escena())
    lejos = escena()
    lejos[50:200, 50:150] = 220  # alguien pasa por la otra punta del gimnasio
    assert d.hay_que_analizar(0.4, lejos) is False


def test_igual_se_analiza_cada_cierto_tiempo():
    d = detector(max_sin_analisis_s=3.0)
    d.hay_que_analizar(0.0, escena(650))
    assert d.hay_que_analizar(2.0, escena(650)) is False
    assert d.hay_que_analizar(3.2, escena(650)) is True
    assert (d.analizados, d.omitidos) == (2, 1)


def test_perfil_rpi_baja_el_ritmo_y_usa_ncnn_y_movimiento():
    from types import SimpleNamespace

    from gymkeep_vision.__main__ import _aplicar_rendimiento
    from gymkeep_vision.config import Config, ConfigCamara, ConfigMaquina

    cfg = Config(camara=ConfigCamara(codigo="CAM"), maquinas=[ConfigMaquina(nombre="M", codigo_activo="EQ", roi=ZONA.tolist())])
    args = SimpleNamespace(perfil="rpi", intervalo=None, imgsz=None, movimiento=False, ncnn=False)
    rpi = _aplicar_rendimiento(cfg, args)
    assert (rpi.intervalo_analisis_s, rpi.modelo.imgsz, rpi.modelo.formato) == (0.4, 640, "ncnn")
    assert rpi.movimiento is not None
    # Una opcion suelta gana sobre el perfil.
    args.intervalo = 0.2
    assert _aplicar_rendimiento(cfg, args).intervalo_analisis_s == 0.2
    # Sin perfil ni opciones no cambia nada.
    sin = SimpleNamespace(perfil=None, intervalo=None, imgsz=None, movimiento=False, ncnn=False)
    assert _aplicar_rendimiento(cfg, sin) is cfg
