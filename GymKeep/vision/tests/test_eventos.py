"""Entrega de eventos: no bloquea el analisis, no pierde datos y conserva el orden."""

import json
import time
from pathlib import Path

import httpx

from gymkeep_vision.__main__ import _cliente
from gymkeep_vision.eventos import DestinoAPI, DestinoJSONL


def evento(n: int) -> dict:
    return {"event_uuid": f"ev-{n}", "evento": {"tipo": "inicio_uso"}, "metadata": {"t_s": n, "t_emision_s": n}}


class ApiFalsa:
    """API que registra los uuid recibidos y puede estar caida o rechazar."""

    def __init__(self):
        self.caida = False
        self.codigo = 201
        self.recibidos: list[str] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        if self.caida:
            raise httpx.ConnectError("sin red")
        if self.codigo >= 300:
            return httpx.Response(self.codigo, json={"detail": "no"})
        self.recibidos.append(json.loads(peticion.read())["event_uuid"])
        return httpx.Response(201, json={"sesion_uso_id": 1})


def destino(api: ApiFalsa, ruta: Path | None = None) -> DestinoAPI:
    cliente = httpx.Client(base_url="http://api", transport=httpx.MockTransport(api))
    return DestinoAPI(cliente, ruta_pendientes=ruta, espera_inicial_s=0.02, espera_max_s=0.05, pausa_s=0.005)


def esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.01)
    return False


def leer_uuids(ruta: Path) -> list[str]:
    return [json.loads(l)["event_uuid"] for l in ruta.read_text().splitlines()]


def test_enviar_no_bloquea_aunque_la_api_este_caida(tmp_path):
    api = ApiFalsa()
    api.caida = True
    d = destino(api, tmp_path / "pend.jsonl")
    try:
        inicio = time.monotonic()
        for n in range(20):
            d.enviar(evento(n))
        assert time.monotonic() - inicio < 0.5
    finally:
        d.cerrar(espera_s=0.3)


def test_api_caida_persiste_pendientes_en_orden_y_los_entrega_al_volver(tmp_path):
    ruta = tmp_path / "pend.jsonl"
    api = ApiFalsa()
    api.caida = True
    d = destino(api, ruta)
    try:
        for n in range(5):
            d.enviar(evento(n))
        assert esperar(lambda: ruta.exists() and len(ruta.read_text().splitlines()) == 5)
        assert leer_uuids(ruta) == [f"ev-{n}" for n in range(5)]
        api.caida = False
        d.enviar(evento(5))  # un evento nuevo no se adelanta a los atrasados
        assert esperar(lambda: len(api.recibidos) == 6)
    finally:
        d.cerrar()
    assert api.recibidos == [f"ev-{n}" for n in range(6)]
    assert d.enviados == 6 and d.pendientes == 0
    assert not ruta.exists()


def test_al_cerrar_con_la_api_caida_quedan_en_disco_y_se_reintentan_al_arrancar(tmp_path):
    ruta = tmp_path / "pend.jsonl"
    api = ApiFalsa()
    api.caida = True
    d = destino(api, ruta)
    for n in range(3):
        d.enviar(evento(n))
    d.cerrar(espera_s=0.3)
    assert leer_uuids(ruta) == ["ev-0", "ev-1", "ev-2"]

    api.caida = False
    d2 = destino(api, ruta)  # nueva corrida: lee los pendientes del archivo
    try:
        assert esperar(lambda: len(api.recibidos) == 3)
    finally:
        d2.cerrar()
    assert api.recibidos == ["ev-0", "ev-1", "ev-2"]
    assert not ruta.exists()


def test_cerrar_drena_la_cola_si_la_api_responde():
    api = ApiFalsa()
    d = destino(api)
    for n in range(10):
        d.enviar(evento(n))
    d.cerrar()
    assert api.recibidos == [f"ev-{n}" for n in range(10)]


def test_evento_rechazado_por_la_api_no_se_reintenta_ni_bloquea_la_cola(tmp_path):
    api = ApiFalsa()
    api.codigo = 422
    d = destino(api, tmp_path / "pend.jsonl")
    d.enviar(evento(1))
    assert esperar(lambda: len(d.fallidos) == 1)
    api.codigo = 201
    d.enviar(evento(2))
    d.cerrar()
    assert api.recibidos == ["ev-2"] and not (tmp_path / "pend.jsonl").exists()


def test_clave_rechazada_se_trata_como_pendiente_no_como_perdida(tmp_path):
    api = ApiFalsa()
    api.codigo = 401
    d = destino(api, tmp_path / "pend.jsonl")
    try:
        d.enviar(evento(1))
        assert esperar(lambda: (tmp_path / "pend.jsonl").exists())
        api.codigo = 201
        assert esperar(lambda: api.recibidos == ["ev-1"])
    finally:
        d.cerrar()
    assert d.fallidos == []


def test_enviar_ahora_devuelve_la_respuesta():
    api = ApiFalsa()
    d = destino(api)
    assert d.enviar_ahora(evento(1)) == {"sesion_uso_id": 1}
    api.caida = True
    assert d.enviar_ahora(evento(2)) is None and len(d.fallidos) == 1
    d.cerrar()


def test_jsonl_abre_en_modo_append(tmp_path):
    ruta = tmp_path / "eventos.jsonl"
    for n in (1, 2):
        local = DestinoJSONL(ruta)
        local.enviar(evento(n))
        local.cerrar()
    assert len(ruta.read_text().splitlines()) == 2


def test_clave_del_pipeline_viaja_en_todas_las_llamadas(monkeypatch):
    monkeypatch.delenv("VISION_PIPELINE_KEY", raising=False)
    assert "x-pipeline-key" not in _cliente("http://api").headers
    assert _cliente("http://api", "secreta").headers["x-pipeline-key"] == "secreta"
    monkeypatch.setenv("VISION_PIPELINE_KEY", "del-entorno")
    assert _cliente("http://api").headers["x-pipeline-key"] == "del-entorno"
    assert _cliente("http://api", "cli").headers["x-pipeline-key"] == "cli"  # la opcion gana

    # El mismo cliente lo usan los eventos y el estado en vivo: la cabecera va en todas.
    vistas = []

    def api(peticion):
        vistas.append(peticion.headers.get("x-pipeline-key"))
        return httpx.Response(200, json={})

    cliente = _cliente("http://api", "secreta")
    cliente._transport = httpx.MockTransport(api)
    cliente.get("/api/v1/vision/camaras/3/configuracion")
    cliente.post("/api/v1/vision/camaras/3/vivo", json={})
    cliente.put("/api/v1/vision/camaras/3/cuadro", content=b"x")
    cliente.post("/api/v1/eventos-ia/", json={})
    assert vistas == ["secreta"] * 4



def test_resolver_ids_pagina_los_listados_de_la_api():
    from gymkeep_vision.config import Config, ConfigCamara, ConfigMaquina
    from gymkeep_vision.eventos import POR_PAGINA, resolver_ids

    equipos = [{"id": i, "codigo_activo": f"EQ-{i}", "sucursal_id": 1} for i in range(1, 702)]
    saltos = []

    def responder(request):
        params = request.url.params
        assert int(params["limit"]) <= POR_PAGINA
        if request.url.path.endswith("/equipamiento/"):
            skip, limit = int(params["skip"]), int(params["limit"])
            saltos.append(skip)
            return httpx.Response(200, json=equipos[skip : skip + limit])
        return httpx.Response(200, json=[])

    cfg = Config(
        camara=ConfigCamara(codigo="CAM-X", id=1, sucursal_id=1, empresa_id=1),
        maquinas=[ConfigMaquina(nombre="M", codigo_activo="EQ-701", roi=[[0, 0], [1, 0], [1, 1]])],
    )
    resolver_ids(httpx.Client(base_url="http://api", transport=httpx.MockTransport(responder)), cfg)
    assert cfg.maquinas[0].equipo_id == 701
    assert saltos == [0, 500]
