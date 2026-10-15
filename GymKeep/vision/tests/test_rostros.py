import numpy as np
import pytest

from gymkeep_vision import rostros
from gymkeep_vision.pipeline import _difuminar_cabezas
from gymkeep_vision.zonas import Deteccion


class RedFalsa:
    """Devuelve una cara fija en coordenadas de la imagen que recibe."""

    def __init__(self, cara):
        self.cara = cara
        self.tam = None

    def setInputSize(self, tam):
        self.tam = tam

    def detect(self, img):
        return 1, np.array([[*self.cara, 0.9]], dtype=np.float32)


def _detector(cara):
    det = rostros.DetectorRostros.__new__(rostros.DetectorRostros)
    det._red = RedFalsa(cara)
    return det


def test_imagen_chica_se_agranda_y_las_cajas_vuelven_a_su_escala():
    det = _detector([200, 100, 40, 40])  # en la imagen agrandada al doble (320 -> 640)
    cajas = det.detectar(np.zeros((240, 320, 3), np.uint8))
    assert det._red.tam == (640, 480)
    assert cajas == [(95, 45, 125, 75)]  # 100..120 con 25 % de margen


def test_cajas_no_salen_de_la_imagen():
    det = _detector([-20, -20, 1300, 760])
    assert det.detectar(np.zeros((720, 1280, 3), np.uint8)) == [(0, 0, 1280, 720)]


def test_sin_modelo_el_pipeline_sigue(monkeypatch):
    def falla(*_):
        raise OSError("sin red")

    monkeypatch.setattr(rostros, "descargar", falla)
    assert rostros.crear() is None


def _ruido():
    return np.random.default_rng(0).integers(0, 255, (200, 200, 3), dtype=np.uint8)


def test_difumina_rostros_que_yolo_no_detecto():
    img, original = _ruido(), _ruido()
    _difuminar_cabezas(img, [], caras=[(10, 10, 60, 60)])
    assert not np.array_equal(img[10:60, 10:60], original[10:60, 10:60])
    assert np.array_equal(img[100:, 100:], original[100:, 100:])


def test_difumina_cabeza_de_persona_y_rostro_escalados():
    img = np.zeros((400, 400, 3), np.uint8)
    img[::2, ::2] = 255
    original = img.copy()
    persona = Deteccion(bbox=(10, 10, 60, 110), confianza=0.9)
    _difuminar_cabezas(img, [persona], f=2.0, caras=[(150, 150, 190, 190)])
    assert not np.array_equal(img[20:80, 20:120], original[20:80, 20:120])  # cabeza x2
    assert not np.array_equal(img[300:380, 300:380], original[300:380, 300:380])  # rostro x2
    assert np.array_equal(img[200:280, 20:120], original[200:280, 20:120])  # cuerpo intacto


@pytest.mark.skipif(not rostros.ruta_modelo().exists(), reason="modelo YuNet no descargado")
def test_modelo_real_no_ve_caras_en_imagen_vacia():
    assert rostros.DetectorRostros().detectar(np.zeros((240, 352, 3), np.uint8)) == []
