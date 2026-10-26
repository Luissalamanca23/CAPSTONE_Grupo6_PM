"""Foto opcional del dano/falla en el reporte por QR (se guarda en Mongo `fotos_incidencias`)."""

import base64
import io

import pytest
from PIL import Image

from app.api.v1 import incidencias as api_incidencias
from app.services import fotos_incidencias


@pytest.fixture(autouse=True)
def _reiniciar_limitadores():
    api_incidencias.limitador_qr_token.reiniciar()
    api_incidencias.limitador_qr_ip.reiniciar()
    yield
    api_incidencias.limitador_qr_token.reiniciar()
    api_incidencias.limitador_qr_ip.reiniciar()


def _foto_b64(tam=(200, 100), formato="PNG", prefijo=""):
    salida = io.BytesIO()
    Image.new("RGB", tam, (200, 40, 40)).save(salida, format=formato)
    return prefijo + base64.b64encode(salida.getvalue()).decode()


def _equipo(client, sucursal_id, codigo="EQ-F1"):
    payload = {"sucursal_id": sucursal_id, "codigo_activo": codigo, "nombre": "Prensa"}
    return client.post("/api/v1/equipamiento/", json=payload).json()


def _reportar(client, token, **extra):
    payload = {"token": token, "tipo_falla_codigo": "ROTA", "gravedad": "grave", "reportado_por": "Socio"}
    payload.update(extra)
    return client.post("/api/v1/incidencias/reporte-qr", json=payload)


def test_reporte_sin_foto_sigue_funcionando(client, sucursal_id):
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    r = _reportar(client, token)
    assert r.status_code == 201
    assert r.json()["tiene_foto"] is False
    assert client.get(f"/api/v1/incidencias/{r.json()['id']}/foto").status_code == 404


def test_reporte_con_foto_la_guarda_y_la_sirve_como_jpeg(client, sucursal_id):
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    r = _reportar(client, token, foto=_foto_b64())
    assert r.status_code == 201
    assert r.json()["tiene_foto"] is True
    foto = client.get(f"/api/v1/incidencias/{r.json()['id']}/foto")
    assert foto.status_code == 200
    assert foto.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(foto.content)).size == (200, 100)


def test_acepta_data_url_y_achica_fotos_grandes(client, sucursal_id):
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    r = _reportar(client, token, foto=_foto_b64((3000, 2000), "JPEG", "data:image/jpeg;base64,"))
    assert r.status_code == 201
    imagen = Image.open(io.BytesIO(client.get(f"/api/v1/incidencias/{r.json()['id']}/foto").content))
    assert max(imagen.size) == 1280


def test_foto_invalida_rechaza_el_reporte_sin_crearlo(client, sucursal_id):
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    basura = base64.b64encode(b"esto no es una imagen").decode()
    r = _reportar(client, token, foto=basura)
    assert r.status_code == 400
    assert client.get("/api/v1/incidencias/").json() == []


def test_listado_marca_cuales_tienen_foto(client, sucursal_id):
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    con = _reportar(client, token, foto=_foto_b64()).json()["id"]
    sin = _reportar(client, token).json()["id"]
    marcas = {i["id"]: i["tiene_foto"] for i in client.get("/api/v1/incidencias/").json()}
    assert marcas == {con: True, sin: False}
    assert client.get(f"/api/v1/incidencias/{con}").json()["tiene_foto"] is True


def test_si_mongo_falla_el_reporte_se_crea_sin_foto(client, sucursal_id, monkeypatch):
    def caido():
        raise RuntimeError("mongo caido")

    monkeypatch.setattr(fotos_incidencias, "get_mongo_db", caido)
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    r = _reportar(client, token, foto=_foto_b64())
    assert r.status_code == 201
    assert r.json()["tiene_foto"] is False
    assert client.get("/api/v1/incidencias/").status_code == 200


def test_eliminar_el_reporte_borra_su_foto(client, sucursal_id, mongo_fotos_incidencias):
    token = _equipo(client, sucursal_id)["qr_activo"]["token"]
    incidencia_id = _reportar(client, token, foto=_foto_b64()).json()["id"]
    assert incidencia_id in mongo_fotos_incidencias.fotos_incidencias.docs
    assert client.delete(f"/api/v1/incidencias/{incidencia_id}").status_code == 204
    assert incidencia_id not in mongo_fotos_incidencias.fotos_incidencias.docs
