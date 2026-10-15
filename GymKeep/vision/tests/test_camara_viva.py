"""Camara en vivo: reconexion, cierre por falta de senal, trabajo perezoso por cuadro,
validacion de la configuracion en caliente y rotacion del registro de presencia.
Sin video ni YOLO: se usa un capturador falso y un modelo falso."""

import sys
import time
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from gymkeep_vision import pipeline as pipeline_mod
from gymkeep_vision.captura import LectorVivo
from gymkeep_vision.config import desde_api
from gymkeep_vision.pipeline import Pipeline, Resultado
from gymkeep_vision.registro import CABECERA, RegistroPresencia
from gymkeep_vision.sesiones import Estado, Observacion
from test_vivo import configuracion


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class CapturaFalsa:
    """Entrega `cuadros` cuadros y despues falla. `abierta=False` simula una camara que no conecta."""

    def __init__(self, cuadros=0, abierta=True):
        self.cuadros, self.abierta, self.liberada = cuadros, abierta, False

    def isOpened(self):
        return self.abierta

    def read(self):
        if self.cuadros > 0:
            self.cuadros -= 1
            return True, np.zeros((480, 640, 3), np.uint8)
        return False, None

    def release(self):
        self.liberada = True


# ---------------------------------------------------------------- reconexion


def test_lector_reabre_con_espera_creciente_hasta_un_tope():
    reloj = Reloj()
    aperturas = []

    def abrir():
        aperturas.append(reloj.t)
        return CapturaFalsa(abierta=False)

    lector = LectorVivo(abrir, CapturaFalsa(cuadros=0), reloj=reloj, espera_max_s=8)
    for _ in range(300):  # 30 s simulados, un intento de lectura cada 0,1 s
        assert lector.leer() == (False, None)
        reloj.t += 0.1
    # Primer corte en t=0: reintentos a +1, +2, +4, +8, +8... segundos.
    esperas = [round(b - a) for a, b in zip([0.0] + aperturas, aperturas)]
    assert esperas[:5] == [1, 2, 4, 8, 8]


def test_lector_se_recupera_y_reinicia_la_espera():
    reloj = Reloj()
    nuevas = [CapturaFalsa(abierta=False), CapturaFalsa(cuadros=1000)]
    lector = LectorVivo(lambda: nuevas.pop(0), CapturaFalsa(cuadros=1), reloj=reloj)
    assert lector.leer()[0] is True
    assert lector.leer()[0] is False  # se corta
    ok = []
    for _ in range(60):
        reloj.t += 0.1
        ok.append(lector.leer()[0])
    assert True in ok and lector.reconexiones == 1
    assert lector.sin_senal_s() < 1


def test_sin_senal_s_cuenta_desde_el_ultimo_cuadro():
    reloj = Reloj()
    lector = LectorVivo(lambda: CapturaFalsa(abierta=False), CapturaFalsa(cuadros=1), reloj=reloj)
    lector.leer()
    reloj.t = 12.0
    assert lector.sin_senal_s() == 12.0


@pytest.fixture()
def pipeline(tmp_path: Path):
    cfg = desde_api(configuracion(t_on_s=30, t_off_s=90))
    p = Pipeline(cfg, "camara.mp4", tmp_path, destinos=[], inicio_video=datetime(2026, 10, 3, tzinfo=timezone.utc))
    p._ancho, p._alto = 1000, 500
    p._preparar_zonas(1000, 500)
    return p, Resultado(cfg, "camara.mp4", p.inicio_video, p.monitores)


def abrir_sesion(monitor, hasta=40.0):
    t = 0.0
    while t <= hasta:
        monitor.actualizar(Observacion(t=t, personas=1, confianza=0.9))
        t += 0.2
    assert monitor.estado == Estado.EN_USO


def test_corte_corto_no_cierra_la_sesion_y_corte_largo_si(pipeline):
    p, resultado = pipeline
    reloj = Reloj()
    lector = LectorVivo(lambda: CapturaFalsa(abierta=False), CapturaFalsa(), reloj=reloj)
    abrir_sesion(p.monitores["Cinta 01"])

    reloj.t = 60.0  # menos que t_off_s
    p._vigilar_senal(lector, 100.0, resultado)
    assert p.monitores["Cinta 01"].sesion is not None and not resultado.eventos

    reloj.t = 91.0
    p._vigilar_senal(lector, 131.0, resultado)
    p._vigilar_senal(lector, 132.0, resultado)  # una sola vez por corte
    assert [e["evento"]["tipo"] for e in resultado.eventos] == ["fin_uso"]
    assert resultado.eventos[0]["metadata"]["cierre"] == "sin_senal"


# ---------------------------------------------------------------- pipeline completo con fakes


class ModeloFalso:
    def __init__(self, *_):
        pass

    def track(self, cuadro, **_):
        return [types.SimpleNamespace(boxes=_Cajas())]


class _Cajas:
    id = types.SimpleNamespace(int=lambda: types.SimpleNamespace(tolist=lambda: [1]))
    xyxy = types.SimpleNamespace(tolist=lambda: [[100.0, 100.0, 150.0, 300.0]])
    conf = types.SimpleNamespace(tolist=lambda: [0.9])

    def __len__(self):
        return 1


class Registro:
    def __init__(self):
        self.eventos = []

    def enviar(self, evento):
        self.eventos.append(evento)


def test_camara_en_vivo_reconecta_cierra_por_senal_y_no_dibuja_de_mas(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=ModeloFalso))

    class Entrega(CapturaFalsa):
        def read(self):
            time.sleep(0.04)
            return super().read()

        def get(self, prop):
            return 25.0 if prop == pipeline_mod.cv2.CAP_PROP_FPS else {3: 640, 4: 480}.get(int(prop), 0)

    primera = Entrega(cuadros=20)
    monkeypatch.setattr(pipeline_mod.cv2, "VideoCapture", lambda *_: primera if not primera.liberada else Entrega(abierta=False))

    cfg = desde_api(configuracion(t_on_s=0.3, t_off_s=0.5, gracia_s=0.1))
    cfg = replace(cfg, intervalo_analisis_s=0.05, difuminar_personas=False)
    destino = Registro()
    p = Pipeline(
        cfg, "camara-falsa", tmp_path, destinos=[destino],
        inicio_video=datetime(2026, 10, 3, tzinfo=timezone.utc), guardar_video=False, max_segundos=2.0,
    )
    dibujos = []
    original = p._anotar
    p._anotar = lambda *a, **k: dibujos.append(1) or original(*a, **k)

    resultado = p.ejecutar()

    tipos = [e["evento"]["tipo"] for e in destino.eventos]
    assert tipos[0] == "inicio_uso" and tipos[-1] == "fin_uso"
    assert destino.eventos[-1]["metadata"]["cierre"] == "sin_senal"
    assert resultado.cuadros_analizados > 5
    # Sin video, ventana ni panel solo se dibuja para la evidencia del inicio_uso.
    assert len(dibujos) == 1
    assert (tmp_path / "presencia.csv").exists()


# ---------------------------------------------------------------- configuracion en caliente


def test_parametros_invalidos_se_ignoran_pero_las_zonas_se_aplican(pipeline):
    p, resultado = pipeline
    monitor = p.monitores["Cinta 01"]
    datos = configuracion(t_on_s=10, t_off_s=1, gracia_s=5)  # t_off_s <= gracia_s
    datos["maquinas"][0]["roi"] = [[0.2, 0.5], [0.5, 0.5], [0.5, 0.95], [0.2, 0.95]]
    p._aplicar_config(datos, 5.0, resultado)
    assert (p.cfg.uso.t_on_s, p.cfg.uso.t_off_s, p.cfg.uso.gracia_s) == (30, 90, 2)
    assert p.monitores["Cinta 01"] is monitor
    assert p.zonas[0].poligono.tolist()[0] == [200.0, 250.0]

    p._aplicar_config(configuracion(t_on_s=10, t_off_s=20, gracia_s=1), 6.0, resultado)
    assert (p.cfg.uso.t_on_s, p.cfg.uso.t_off_s) == (10, 20)
    assert monitor.p is p.cfg.uso


def test_maquinas_sin_equipo_id_se_emparejan_por_nombre(pipeline):
    p, resultado = pipeline
    p.maquinas["Cinta 01"].equipo_id = None  # venia de un YAML sin equipo_id
    monitor = p.monitores["Cinta 01"]
    abrir_sesion(monitor)
    p._aplicar_config(configuracion(), 40.0, resultado)  # ahora la plataforma le da equipo_id 7
    assert p.monitores["Cinta 01"] is monitor and monitor.sesion is not None
    assert not resultado.eventos


# ---------------------------------------------------------------- presencia.csv en vivo


def fila(dia, n=0):
    return [f"{n}.00", f"2026-10-{dia:02d}T10:00:00.000-03:00", "Cinta 01", 1, "0.900", "en_uso"]


def test_presencia_de_archivo_no_rota(tmp_path):
    reg = RegistroPresencia(tmp_path / "presencia.csv", max_bytes=10)
    for n in range(50):
        reg.escribir(fila(1 + n % 3, n))
    reg.cerrar()
    assert [f.name for f in tmp_path.iterdir()] == ["presencia.csv"]
    assert len((tmp_path / "presencia.csv").read_text().splitlines()) == 51


def test_presencia_en_vivo_rota_por_dia_y_por_tamano_y_acota_los_archivos(tmp_path):
    reg = RegistroPresencia(tmp_path / "presencia.csv", rotar=True, max_bytes=300, max_archivos=3)
    for n in range(40):
        reg.escribir(fila(1, n))
    reg.escribir(fila(2, 99))  # cambia el dia
    reg.cerrar()
    nombres = sorted(f.name for f in tmp_path.iterdir())
    assert "presencia.csv" in nombres and len(nombres) == 4  # vigente + 3 archivados como maximo
    vigente = (tmp_path / "presencia.csv").read_text().splitlines()
    assert vigente[0] == ",".join(CABECERA) and len(vigente) == 2  # cabecera + la fila del dia 2


def test_presencia_en_vivo_archiva_lo_de_la_corrida_anterior(tmp_path):
    (tmp_path / "presencia.csv").write_text(",".join(CABECERA) + "\n" + ",".join(map(str, fila(1))) + "\n")
    reg = RegistroPresencia(tmp_path / "presencia.csv", rotar=True)
    reg.cerrar()
    assert len(list(tmp_path.glob("presencia.*.csv"))) == 1
