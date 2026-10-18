"""Clave del pipeline (X-Pipeline-Key), PIN en las fotos y parametro t_max_s."""

import uuid
from datetime import datetime, timezone

import pytest

from app.core import pin
from app.core.config import settings
from app.models.gymkeep import Camara, EstadoCamara
from tests.test_vision_api import ZONA, camara_y_equipo, estado_vivo, imagen, mongo  # noqa: F401 (fixtures)

CLAVE = "clave-del-pipeline"
PIN = "4821"
VALORES = {"t_on_s": 30, "t_off_s": 90, "confianza_min": 0.5, "gracia_s": 2, "escala_tiempo": 1.0}


@pytest.fixture()
def con_clave(monkeypatch):
    monkeypatch.setattr(settings, "vision_pipeline_key", CLAVE)
    return {"X-Pipeline-Key": CLAVE}


@pytest.fixture()
def con_pin(monkeypatch):
    monkeypatch.setattr(settings, "vision_pin", PIN)
    pin.reiniciar_intentos()
    yield {"X-Vision-Pin": PIN}
    pin.reiniciar_intentos()


def evento_ia(equipo_id, camara_id):
    return {
        "event_uuid": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "camara_id": camara_id,
        "equipo_id": equipo_id,
        "modelo": {"nombre": "gymkeep-usage-detector", "version": "0.1.0"},
        "evento": {"tipo": "persona_detectada", "confidence": 0.9},
    }


def test_sin_clave_configurada_los_endpoints_del_pipeline_quedan_abiertos(client, mongo, camara_y_equipo):
    camara_id, equipo_id = camara_y_equipo
    assert client.get(f"/api/v1/vision/camaras/{camara_id}/configuracion").status_code == 200
    assert client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id)).status_code == 202


def test_endpoints_del_pipeline_piden_la_clave(client, mongo, camara_y_equipo, con_clave):
    camara_id, equipo_id = camara_y_equipo
    config = f"/api/v1/vision/camaras/{camara_id}/configuracion"
    vivo = f"/api/v1/vision/camaras/{camara_id}/vivo"

    assert client.get(config).status_code == 401
    assert client.get(config, headers={"X-Pipeline-Key": "otra"}).status_code == 401
    assert client.get(config, headers=con_clave).status_code == 200
    assert client.post(vivo, json=estado_vivo(equipo_id)).status_code == 401
    assert client.post(vivo, json=estado_vivo(equipo_id), headers=con_clave).status_code == 202

    # Lo que consulta el panel sigue sin clave.
    assert client.get(vivo).status_code == 200
    assert client.get("/api/v1/vision/camaras").status_code == 200


def test_eventos_ia_piden_la_clave(client, camara_y_equipo, con_clave, monkeypatch):
    from tests.test_eventos_ia import MongoFalso
    from app.services import ai_event_service

    monkeypatch.setattr(ai_event_service, "get_mongo_db", lambda: MongoFalso())
    camara_id, equipo_id = camara_y_equipo
    cuerpo = evento_ia(equipo_id, camara_id)
    assert client.post("/api/v1/eventos-ia/", json=cuerpo).status_code == 401
    assert client.post("/api/v1/eventos-ia/", json=cuerpo, headers=con_clave).status_code == 201


def test_el_cuadro_acepta_la_clave_o_el_pin(client, mongo, camara_y_equipo, con_clave, con_pin):
    camara_id, _ = camara_y_equipo
    url = f"/api/v1/vision/camaras/{camara_id}/cuadro"
    assert client.put(url, content=imagen()).status_code == 401
    assert client.put(url, content=imagen(), headers={"X-Pipeline-Key": "otra"}).status_code == 401
    assert client.put(url, content=imagen(), headers=con_clave).status_code == 201
    assert client.put(url, content=imagen(), headers=con_pin).status_code == 201


def test_el_cuadro_con_solo_clave_configurada_no_queda_abierto(client, mongo, camara_y_equipo, con_clave):
    camara_id, _ = camara_y_equipo
    url = f"/api/v1/vision/camaras/{camara_id}/cuadro"
    assert client.put(url, content=imagen()).status_code == 401
    assert client.put(url, content=imagen(), headers=con_clave).status_code == 201


def test_el_cuadro_con_solo_pin_configurado(client, mongo, camara_y_equipo, con_pin):
    camara_id, _ = camara_y_equipo
    url = f"/api/v1/vision/camaras/{camara_id}/cuadro"
    assert client.put(url, content=imagen()).status_code == 401
    assert client.put(url, content=imagen(), headers=con_pin).status_code == 201


def test_las_fotos_de_maquinas_piden_el_pin(client, mongo, camara_y_equipo, con_pin):
    camara_id, equipo_id = camara_y_equipo
    foto = f"/api/v1/vision/maquinas/{equipo_id}/foto"
    client.put(f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}", json=ZONA, headers=con_pin)
    client.put(f"/api/v1/vision/camaras/{camara_id}/cuadro", content=imagen("JPEG", (640, 360)), headers=con_pin)

    assert client.put(foto, content=imagen()).status_code == 401
    assert client.post(f"{foto}/desde-camara").status_code == 401
    assert client.put(foto, content=imagen(), headers=con_pin).status_code == 201
    assert client.post(f"{foto}/desde-camara", headers=con_pin).status_code == 201
    assert client.get(foto).status_code == 200  # verla no pide PIN


@pytest.mark.parametrize("estado", [EstadoCamara.mantenimiento, EstadoCamara.inactiva])
def test_enviar_datos_no_reactiva_una_camara_en_mantenimiento_o_inactiva(
    client, mongo, camara_y_equipo, db_session, estado
):
    camara_id, equipo_id = camara_y_equipo
    db_session.get(Camara, camara_id).estado = estado
    db_session.commit()
    client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id))
    db_session.expire_all()
    camara = db_session.get(Camara, camara_id)
    assert camara.estado == estado
    assert camara.ultima_conexion is not None  # la conexion si se registra


def test_una_camara_con_error_vuelve_a_activa_al_enviar_datos(client, mongo, camara_y_equipo, db_session):
    camara_id, equipo_id = camara_y_equipo
    db_session.get(Camara, camara_id).estado = EstadoCamara.error
    db_session.commit()
    client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id))
    db_session.expire_all()
    assert db_session.get(Camara, camara_id).estado == EstadoCamara.activa


def test_t_max_s_viaja_en_los_parametros_y_la_configuracion(client, mongo, camara_y_equipo):
    camara_id, _ = camara_y_equipo
    assert client.get(f"/api/v1/vision/camaras/{camara_id}").json()["parametros"]["t_max_s"] == 10800

    url = f"/api/v1/vision/camaras/{camara_id}/parametros"
    assert client.put(url, json={**VALORES, "t_max_s": 7200}).json()["t_max_s"] == 7200
    config = client.get(f"/api/v1/vision/camaras/{camara_id}/configuracion").json()
    assert config["parametros"]["t_max_s"] == 7200

    assert client.put(url, json={**VALORES, "t_max_s": 599}).status_code == 422
    assert client.put(url, json={**VALORES, "t_max_s": 86401}).status_code == 422
    assert client.put(url, json=VALORES).json()["t_max_s"] == 10800  # sin enviarlo, el valor por defecto
