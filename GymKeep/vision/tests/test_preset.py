"""Zonas iniciales de una camara (preset) y espera a la API, contra una API simulada."""

import json
from pathlib import Path

import httpx
import pytest

from gymkeep_vision import preset

PRESET = Path(__file__).resolve().parents[1] / "config" / "zonas_cintas.json"


class ApiFalsa:
    def __init__(self, equipos):
        self.equipos = {e["codigo_activo"]: e for e in equipos}
        self.zonas = {}
        self.creados = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        ruta = request.url.path
        if request.method == "GET" and ruta == "/api/v1/equipamiento/":
            return httpx.Response(200, json=list(self.equipos.values()))
        if request.method == "POST" and ruta == "/api/v1/equipamiento/":
            datos = json.loads(request.content)
            equipo = {"id": 100 + len(self.creados), **datos}
            self.equipos[datos["codigo_activo"]] = equipo
            self.creados.append(datos["codigo_activo"])
            return httpx.Response(201, json=equipo)
        if request.method == "PUT" and "/maquinas/" in ruta:
            self.zonas[int(ruta.rsplit("/", 1)[1])] = json.loads(request.content)["puntos"]
            return httpx.Response(200, json={})
        return httpx.Response(404)


def cliente(api):
    return httpx.Client(base_url="http://api", transport=httpx.MockTransport(api))


CAMARA = {"id": 3, "codigo": "CAM-01", "sucursal_id": 1, "zona_id": 2}


def test_el_preset_de_las_cintas_es_valido():
    datos = preset.leer_preset(PRESET)
    assert datos["camara"] == "CAM-01" and len(datos["maquinas"]) == 3
    for maquina in datos["maquinas"]:
        assert len(maquina["puntos"]) >= 3
        assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in maquina["puntos"])


def test_aplica_las_zonas_y_crea_los_equipos_que_faltan():
    api = ApiFalsa([{"id": 1, "codigo_activo": "EQ-0001"}])
    assert preset.aplicar(cliente(api), CAMARA, preset.leer_preset(PRESET)) == 3
    assert api.creados == ["EQ-0002", "EQ-0014"]
    assert set(api.zonas) == {1, 100, 101}


def test_sin_crear_omite_los_equipos_que_no_existen():
    api = ApiFalsa([{"id": 1, "codigo_activo": "EQ-0001"}])
    assert preset.aplicar(cliente(api), CAMARA, preset.leer_preset(PRESET), crear_equipos=False) == 1
    assert api.creados == [] and set(api.zonas) == {1}


def test_esperar_api_reintenta_hasta_que_responde(monkeypatch):
    monkeypatch.setattr(preset.time, "sleep", lambda s: None)
    intentos = []

    def manejador(request):
        intentos.append(1)
        if len(intentos) < 3:
            raise httpx.ConnectError("sin conexion")
        return httpx.Response(200, json=[])

    preset.esperar_api(httpx.Client(base_url="http://api", transport=httpx.MockTransport(manejador)), 60)
    assert len(intentos) == 3


def test_esperar_api_se_rinde_al_vencer_el_plazo(monkeypatch):
    monkeypatch.setattr(preset.time, "sleep", lambda s: None)

    def caida(request):
        raise httpx.ConnectError("sin conexion")

    cliente_caido = httpx.Client(base_url="http://api", transport=httpx.MockTransport(caida))
    with pytest.raises(RuntimeError, match="no responde"):
        preset.esperar_api(cliente_caido, 0.01)
