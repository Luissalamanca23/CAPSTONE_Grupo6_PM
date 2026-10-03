"""Eventos del modulo de vision -> sesiones_uso -> horometro (etapas 3 a 5 de §6.6.1)."""

import uuid

import pytest
from pymongo.errors import DuplicateKeyError

from app.services import ai_event_service


class ColeccionFalsa:
    def __init__(self):
        self.docs = {}

    def insert_one(self, doc):
        if doc["event_uuid"] in self.docs:
            raise DuplicateKeyError("duplicado")
        self.docs[doc["event_uuid"]] = doc


class MongoFalso:
    def __init__(self):
        self.eventos_ia = ColeccionFalsa()


@pytest.fixture()
def mongo(monkeypatch):
    falso = MongoFalso()
    monkeypatch.setattr(ai_event_service, "get_mongo_db", lambda: falso)
    return falso


@pytest.fixture()
def equipo_y_camara(client, sucursal_id, zona_id):
    equipo = client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "zona_id": zona_id, "codigo_activo": "EQ-CAM-1", "nombre": "Cinta 01"},
    ).json()
    camara = client.post(
        "/api/v1/camaras/",
        json={"codigo": "CAM-01", "nombre": "Camara Cardio", "sucursal_id": sucursal_id, "equipo_ids": [equipo["id"]]},
    ).json()
    return equipo["id"], camara["id"]


def evento(tipo, timestamp, equipo_id, camara_id, confidence=0.9, **metadata):
    return {
        "event_uuid": str(uuid.uuid4()),
        "timestamp": timestamp,
        "camara_id": camara_id,
        "equipo_id": equipo_id,
        "modelo": {"nombre": "gymkeep-usage-detector", "version": "0.1.0"},
        "evento": {"tipo": tipo, "confidence": confidence},
        "metadata": metadata,
    }


def test_inicio_y_fin_de_uso_crean_una_sesion_cerrada(client, mongo, equipo_y_camara):
    equipo_id, camara_id = equipo_y_camara
    inicio = client.post(
        "/api/v1/eventos-ia/",
        json=evento("inicio_uso", "2026-09-26T18:00:00-03:00", equipo_id, camara_id, sesion_ref="abc"),
    ).json()
    assert inicio["procesado"] is True
    assert inicio["sesion_uso_id"] is not None

    en_curso = client.post(
        "/api/v1/eventos-ia/", json=evento("uso_en_curso", "2026-09-26T18:01:00-03:00", equipo_id, camara_id)
    ).json()
    fin = client.post(
        "/api/v1/eventos-ia/",
        json=evento(
            "fin_uso", "2026-09-26T18:12:30-03:00", equipo_id, camara_id, confidence=0.87,
            presencia_segundos=610.0, pausas=3, cierre="ausencia",
        ),
    ).json()
    assert en_curso["sesion_uso_id"] == fin["sesion_uso_id"] == inicio["sesion_uso_id"]

    sesiones = client.get("/api/v1/sesiones-uso/", params={"equipo_id": equipo_id}).json()
    assert len(sesiones) == 1
    sesion = sesiones[0]
    assert sesion["estado"] == "cerrada"
    assert sesion["duracion_segundos"] == 750
    assert sesion["cantidad_eventos"] == 3
    assert sesion["confianza_promedio"] == pytest.approx(0.87)
    assert sesion["metadata"]["sesion_ref"] == "abc"
    assert sesion["metadata"]["pausas"] == 3
    assert len(mongo.eventos_ia.docs) == 3


def test_reenviar_el_mismo_evento_es_idempotente(client, mongo, equipo_y_camara):
    equipo_id, camara_id = equipo_y_camara
    payload = evento("inicio_uso", "2026-09-26T18:00:00-03:00", equipo_id, camara_id)
    primero = client.post("/api/v1/eventos-ia/", json=payload)
    segundo = client.post("/api/v1/eventos-ia/", json=payload)
    assert primero.status_code == segundo.status_code == 201
    assert primero.json()["id"] == segundo.json()["id"]
    assert len(client.get("/api/v1/sesiones-uso/").json()) == 1


def test_evento_que_quedo_en_mongo_pero_no_en_postgres_se_completa(client, mongo, equipo_y_camara):
    equipo_id, camara_id = equipo_y_camara
    payload = evento("inicio_uso", "2026-09-26T18:00:00-03:00", equipo_id, camara_id)
    mongo.eventos_ia.docs[payload["event_uuid"]] = payload  # intento anterior a medias
    respuesta = client.post("/api/v1/eventos-ia/", json=payload)
    assert respuesta.status_code == 201
    assert respuesta.json()["sesion_uso_id"] is not None


def test_fin_sin_inicio_queda_sin_procesar(client, mongo, equipo_y_camara):
    equipo_id, camara_id = equipo_y_camara
    fin = client.post(
        "/api/v1/eventos-ia/", json=evento("fin_uso", "2026-09-26T18:12:30-03:00", equipo_id, camara_id)
    ).json()
    assert fin["procesado"] is False
    assert fin["sesion_uso_id"] is None


def test_inicio_huerfano_se_descarta_al_llegar_otro_inicio(client, mongo, equipo_y_camara):
    equipo_id, camara_id = equipo_y_camara
    client.post("/api/v1/eventos-ia/", json=evento("inicio_uso", "2026-09-26T18:00:00-03:00", equipo_id, camara_id))
    client.post("/api/v1/eventos-ia/", json=evento("inicio_uso", "2026-09-26T19:00:00-03:00", equipo_id, camara_id))
    estados = sorted(s["estado"] for s in client.get("/api/v1/sesiones-uso/").json())
    assert estados == ["abierta", "descartada"]


def test_sesion_con_eventos_intermedios_se_cierra_forzada_en_el_ultimo_evento(client, mongo, equipo_y_camara):
    equipo_id, camara_id = equipo_y_camara
    client.post("/api/v1/eventos-ia/", json=evento("inicio_uso", "2026-09-26T18:00:00-03:00", equipo_id, camara_id))
    client.post("/api/v1/eventos-ia/", json=evento("uso_en_curso", "2026-09-26T18:05:00-03:00", equipo_id, camara_id))
    # Se perdio el fin_uso (se reinicio el pipeline) y llega un nuevo inicio.
    client.post("/api/v1/eventos-ia/", json=evento("inicio_uso", "2026-09-26T19:00:00-03:00", equipo_id, camara_id))
    cerrada = client.get("/api/v1/sesiones-uso/", params={"estado": "cerrada"}).json()
    assert len(cerrada) == 1
    assert cerrada[0]["duracion_segundos"] == 300
    assert cerrada[0]["metadata"]["cierre"] == "forzado"


def test_horometro_cuenta_la_union_de_intervalos(client, mongo, equipo_y_camara, sucursal_id):
    equipo_id, camara_id = equipo_y_camara
    otra_camara = client.post(
        "/api/v1/camaras/",
        json={"codigo": "CAM-02", "nombre": "Camara 2", "sucursal_id": sucursal_id, "equipo_ids": [equipo_id]},
    ).json()["id"]
    # Dos camaras ven la misma sesion con distinto margen: 18:00-18:30 y 18:10-18:40.
    for cam, ini, fin in [(camara_id, "18:00", "18:30"), (otra_camara, "18:10", "18:40")]:
        client.post("/api/v1/eventos-ia/", json=evento("inicio_uso", f"2026-09-26T{ini}:00-03:00", equipo_id, cam))
        client.post("/api/v1/eventos-ia/", json=evento("fin_uso", f"2026-09-26T{fin}:00-03:00", equipo_id, cam))

    fila = client.get("/api/v1/sesiones-uso/horometro", params={"equipo_id": equipo_id}).json()[0]
    assert fila["sesiones_cerradas"] == 2
    assert fila["horas_suma"] == pytest.approx(1.0)
    assert fila["horas_uso"] == pytest.approx(40 / 60, abs=1e-3)  # no 1 h: se solapan 20 min
