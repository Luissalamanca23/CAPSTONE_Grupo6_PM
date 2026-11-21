"""Zonas iniciales de una camara (preset) y espera a la API, contra una API simulada."""

import json
from pathlib import Path

import httpx
import pytest

from gymkeep_vision import preset

PRESET = Path(__file__).resolve().parents[1] / "config" / "zonas_cintas.json"


def _listado_como_la_api(request: httpx.Request, filas: list[dict]) -> httpx.Response:
    """Como GET /equipamiento/ de la API real: limit entre 1 y 500 (si no, 422) y paginacion con skip."""
    limite = int(request.url.params.get("limit", 100))
    if not 1 <= limite <= 500:
        return httpx.Response(422, json={"detail": "limit fuera de rango (1 a 500)"})
    saltar = int(request.url.params.get("skip", 0))
    return httpx.Response(200, json=filas[saltar : saltar + limite])


class ApiFalsa:
    def __init__(self, equipos):
        self.equipos = {e["codigo_activo"]: e for e in equipos}
        self.zonas = {}
        self.creados = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        ruta = request.url.path
        if request.method == "GET" and ruta == "/api/v1/equipamiento/":
            return _listado_como_la_api(request, list(self.equipos.values()))
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


# ---- camaras y parametros del preset (demo con 3 videos) ----

CONFIG = Path(__file__).resolve().parents[1] / "config"
PRESETS_DEMO = ["zonas_video1_cctv.json", "zonas_video2_gym.json", "zonas_video3_tramoA.json"]


class ApiConCamaras:
    """API simulada con sucursales, zonas, camaras, equipos y parametros."""

    def __init__(self, sucursales=None, zonas=None, camaras=None):
        self.sucursales = sucursales if sucursales is not None else [{"id": 1, "codigo": "PM-01"}]
        self.zonas = zonas if zonas is not None else []
        self.camaras = camaras if camaras is not None else []
        self.equipos = {}
        self.puestas = {}
        self.parametros = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        ruta, metodo = request.url.path, request.method
        cuerpo = json.loads(request.content) if request.content else None
        if metodo == "GET" and ruta == "/api/v1/vision/camaras":
            return httpx.Response(200, json=self.camaras)
        if metodo == "GET" and ruta == "/api/v1/sucursales/":
            return httpx.Response(200, json=self.sucursales)
        if metodo == "GET" and ruta == "/api/v1/zonas/":
            return httpx.Response(200, json=self.zonas)
        if metodo == "POST" and ruta == "/api/v1/zonas/":
            zona = {"id": 40 + len(self.zonas), **cuerpo}
            self.zonas.append(zona)
            return httpx.Response(201, json=zona)
        if metodo == "POST" and ruta == "/api/v1/camaras/":
            camara = {"id": 7 + len(self.camaras), "sucursal_id": cuerpo["sucursal_id"], "zona_id": cuerpo["zona_id"], "codigo": cuerpo["codigo"], "nombre": cuerpo["nombre"]}
            self.camaras.append(camara)
            return httpx.Response(201, json=camara)
        if metodo == "GET" and ruta == "/api/v1/equipamiento/":
            return _listado_como_la_api(request, list(self.equipos.values()))
        if metodo == "POST" and ruta == "/api/v1/equipamiento/":
            equipo = {"id": 100 + len(self.equipos), **cuerpo}
            self.equipos[cuerpo["codigo_activo"]] = equipo
            return httpx.Response(201, json=equipo)
        if metodo == "PUT" and "/maquinas/" in ruta:
            self.puestas[int(ruta.rsplit("/", 1)[1])] = cuerpo["puntos"]
            return httpx.Response(200, json={})
        if metodo == "PUT" and ruta.endswith("/parametros"):
            self.parametros[int(ruta.split("/")[-2])] = cuerpo
            return httpx.Response(200, json=cuerpo)
        return httpx.Response(404)


@pytest.mark.parametrize("archivo", PRESETS_DEMO)
def test_los_presets_de_la_demo_son_validos(archivo):
    datos = preset.leer_preset(CONFIG / archivo)
    assert datos["camara"].startswith("CAM-")
    assert datos["crear_camara"]["nombre"] and datos["crear_camara"]["sucursal_codigo"]
    par = datos["parametros"]
    assert par["t_on_s"] == 30 and par["t_off_s"] == 90 and par["confianza_min"] == 0.25 and par["gracia_s"] == 10
    assert par["t_off_s"] > par["gracia_s"] and par["escala_tiempo"] > 0
    for maquina in datos["maquinas"]:
        assert len(maquina["puntos"]) >= 3
        assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in maquina["puntos"])


def test_las_camaras_y_los_equipos_de_los_3_presets_no_se_repiten():
    presets = [preset.leer_preset(CONFIG / a) for a in PRESETS_DEMO]
    camaras = [d["camara"] for d in presets]
    codigos = [m["codigo_activo"] for d in presets for m in d["maquinas"]]
    assert len(set(camaras)) == 3
    assert len(set(codigos)) == len(codigos) == 8


def test_crea_la_camara_con_su_zona_y_aplica_zonas_y_parametros():
    api = ApiConCamaras()
    datos = preset.leer_preset(CONFIG / "zonas_video3_tramoA.json")
    c = cliente(api)
    camara = preset.asegurar_camara(c, datos["camara"], datos)
    assert camara["codigo"] == "CAM-GYM-02" and camara["sucursal_id"] == 1
    assert [z["nombre"] for z in api.zonas] == ["Musculacion"] and camara["zona_id"] == api.zonas[0]["id"]
    assert preset.aplicar(c, camara, datos) == 2
    assert set(api.equipos) == {"EQ-RS-02", "EQ-BA-01"}
    assert api.parametros[camara["id"]] == datos["parametros"]


def test_si_la_camara_ya_existe_no_se_crea_otra():
    existente = {"id": 5, "codigo": "CAM-GYM-02", "sucursal_id": 1, "zona_id": 2}
    api = ApiConCamaras(camaras=[existente])
    datos = preset.leer_preset(CONFIG / "zonas_video3_tramoA.json")
    assert preset.asegurar_camara(cliente(api), "CAM-GYM-02", datos) == existente
    assert len(api.camaras) == 1 and api.zonas == []


def test_reutiliza_la_zona_que_ya_existe_sin_importar_mayusculas():
    api = ApiConCamaras(zonas=[{"id": 9, "nombre": "musculacion", "sucursal_id": 1}])
    datos = preset.leer_preset(CONFIG / "zonas_video2_gym.json")
    camara = preset.asegurar_camara(cliente(api), datos["camara"], datos)
    assert camara["zona_id"] == 9 and len(api.zonas) == 1


def test_con_una_sola_sucursal_usa_esa_aunque_el_codigo_no_coincida():
    api = ApiConCamaras(sucursales=[{"id": 4, "codigo": "CAF-PM"}])
    datos = preset.leer_preset(CONFIG / "zonas_video1_cctv.json")
    assert preset.asegurar_camara(cliente(api), datos["camara"], datos)["sucursal_id"] == 4


def test_con_varias_sucursales_y_codigo_desconocido_falla():
    api = ApiConCamaras(sucursales=[{"id": 1, "codigo": "A"}, {"id": 2, "codigo": "B"}])
    datos = preset.leer_preset(CONFIG / "zonas_video1_cctv.json")
    with pytest.raises(RuntimeError, match="No existe la sucursal"):
        preset.asegurar_camara(cliente(api), datos["camara"], datos)


def test_un_preset_sin_crear_camara_sigue_exigiendo_que_la_camara_exista():
    api = ApiConCamaras()
    datos = {"camara": "CAM-99", "maquinas": [{"codigo_activo": "X", "puntos": [[0, 0], [1, 0], [1, 1]]}]}
    with pytest.raises(RuntimeError, match="No existe la camara"):
        preset.asegurar_camara(cliente(api), "CAM-99", datos)


def test_aplicar_encuentra_equipos_existentes_mas_alla_de_la_primera_pagina():
    """La API entrega como maximo 500 equipos por pagina: aplicar debe leer todas las paginas y no crear de nuevo un equipo ya existente."""
    equipos = [{"id": i, "codigo_activo": f"X-{i:04d}"} for i in range(1, 601)]
    equipos.append({"id": 700, "codigo_activo": "EQ-RS-02", "nombre": "Remo ya existente"})
    api = ApiFalsa(equipos)
    datos = {"maquinas": [{"codigo_activo": "EQ-RS-02", "nombre": "Remo sentado 2", "puntos": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]}]}
    assert preset.aplicar(cliente(api), {"id": 7, "sucursal_id": 1, "codigo": "CAM-GYM-02"}, datos) == 1
    assert api.creados == []
    assert 700 in api.zonas
