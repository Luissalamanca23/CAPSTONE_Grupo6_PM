"""PIN de edicion de zonas y parametros del modulo de vision (app/core/pin.py)."""

import pytest
from pydantic import ValidationError

from app.core import pin
from app.core.config import Settings, settings
from tests.test_vision_api import ZONA, camara_y_equipo, mongo  # noqa: F401 (fixtures)


@pytest.fixture()
def con_pin(monkeypatch):
    monkeypatch.setattr(settings, "vision_pin", "4821")
    pin.reiniciar_intentos()
    yield "4821"
    pin.reiniciar_intentos()


def test_sin_pin_configurado_la_edicion_es_libre(client, mongo, camara_y_equipo, monkeypatch):
    monkeypatch.setattr(settings, "vision_pin", "")
    camara_id, equipo_id = camara_y_equipo
    assert client.get("/api/v1/vision/pin").json() == {"requerido": False}
    assert client.put(f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}", json=ZONA).status_code == 200


def test_editar_zonas_y_parametros_pide_el_pin(client, mongo, camara_y_equipo, con_pin):
    camara_id, equipo_id = camara_y_equipo
    zona = f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}"
    parametros = f"/api/v1/vision/camaras/{camara_id}/parametros"
    valores = {"t_on_s": 30, "t_off_s": 90, "confianza_min": 0.5, "gracia_s": 2, "escala_tiempo": 1.0}

    assert client.get("/api/v1/vision/pin").json() == {"requerido": True}
    assert client.put(zona, json=ZONA).status_code == 401
    assert client.put(zona, json=ZONA, headers={"X-Vision-Pin": "0000"}).status_code == 401

    ok = {"X-Vision-Pin": con_pin}
    assert client.put(zona, json=ZONA, headers=ok).status_code == 200
    assert client.put(parametros, json=valores).status_code == 401
    assert client.put(parametros, json=valores, headers=ok).status_code == 200
    assert client.delete(zona).status_code == 401
    assert client.delete(zona, headers=ok).status_code == 204


def test_ver_camaras_y_el_pipeline_no_piden_pin(client, mongo, camara_y_equipo, con_pin):
    camara_id, _ = camara_y_equipo
    assert client.get(f"/api/v1/vision/camaras/{camara_id}").status_code == 200
    assert client.get(f"/api/v1/vision/camaras/{camara_id}/configuracion").status_code == 200
    assert client.get("/api/v1/vision/maquinas").status_code == 200


def test_verificar_pin(client, con_pin):
    assert client.post("/api/v1/vision/pin/verificar", headers={"X-Vision-Pin": con_pin}).status_code == 204
    assert client.post("/api/v1/vision/pin/verificar", headers={"X-Vision-Pin": "1234"}).status_code == 401


def test_bloqueo_tras_intentos_fallidos(client, con_pin):
    for _ in range(pin.INTENTOS_MAX):
        assert client.post("/api/v1/vision/pin/verificar", headers={"X-Vision-Pin": "1111"}).status_code == 401
    # Bloqueada: ni siquiera el PIN correcto entra hasta que pase el tiempo.
    assert client.post("/api/v1/vision/pin/verificar", headers={"X-Vision-Pin": con_pin}).status_code == 429


@pytest.mark.parametrize("valor", ["123", "1234567", "12a4"])
def test_pin_mal_configurado_se_rechaza(valor):
    with pytest.raises(ValidationError):
        Settings(vision_pin=valor)


def test_pin_valido_se_acepta():
    assert Settings(vision_pin=" 123456 ").vision_pin == "123456"
