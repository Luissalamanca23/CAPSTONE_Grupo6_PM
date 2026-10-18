import pytest

from app.api.v1 import incidencias as api_incidencias


@pytest.fixture(autouse=True)
def _reiniciar_limitadores():
    api_incidencias.limitador_qr_token.reiniciar()
    api_incidencias.limitador_qr_ip.reiniciar()
    yield
    api_incidencias.limitador_qr_token.reiniciar()
    api_incidencias.limitador_qr_ip.reiniciar()


def _crear_equipo(client, sucursal_id, codigo_activo):
    payload = {"sucursal_id": sucursal_id, "codigo_activo": codigo_activo, "nombre": "Cinta"}
    return client.post("/api/v1/equipamiento/", json=payload).json()


def _reportar(client, token, **extra):
    payload = {"token": token, "tipo_falla_codigo": "ROTA", "gravedad": "grave", "reportado_por": "Socio"}
    payload.update(extra)
    return client.post("/api/v1/incidencias/reporte-qr", json=payload)


def _estado_equipo(client, equipo_id):
    return client.get(f"/api/v1/equipamiento/{equipo_id}").json()["estado"]


def test_un_solo_reporte_no_funcional_no_deja_el_equipo_fuera_de_servicio(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-P100")
    respuesta = _reportar(client, equipo["qr_activo"]["token"], funcional=False)
    assert respuesta.status_code == 201
    assert respuesta.json()["prioridad"] == "urgente"
    assert _estado_equipo(client, equipo["id"]) == "operativo"


def test_dos_reportes_no_funcional_dejan_el_equipo_fuera_de_servicio(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-P101")
    token = equipo["qr_activo"]["token"]
    _reportar(client, token, funcional=False)
    _reportar(client, token, funcional=False)
    assert _estado_equipo(client, equipo["id"]) == "fuera_de_servicio"


def test_reportes_que_si_funcionan_no_cuentan_para_fuera_de_servicio(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-P102")
    token = equipo["qr_activo"]["token"]
    _reportar(client, token, funcional=False)
    _reportar(client, token, funcional=True)
    assert _estado_equipo(client, equipo["id"]) == "operativo"


def test_reporte_qr_rechaza_textos_demasiado_largos(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-P103")
    token = equipo["qr_activo"]["token"]
    assert _reportar(client, token, reportado_por="x" * 81).status_code == 422
    assert _reportar(client, token, descripcion="x" * 1001).status_code == 422
    assert _reportar(client, token, reportado_por="x" * 80, descripcion="x" * 1000).status_code == 201


def test_reporte_qr_limita_la_frecuencia_por_token(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-P104")
    otro = _crear_equipo(client, sucursal_id, "EQ-P105")
    token = equipo["qr_activo"]["token"]
    for _ in range(5):
        assert _reportar(client, token, funcional=True).status_code == 201
    bloqueado = _reportar(client, token)
    assert bloqueado.status_code == 429
    assert "demasiados reportes" in bloqueado.json()["detail"]
    # Otro equipo (otro token) no queda afectado.
    assert _reportar(client, otro["qr_activo"]["token"]).status_code == 201


def test_listados_rechazan_limit_fuera_de_rango(client):
    for ruta in ("incidencias", "equipamiento", "empresas", "sucursales", "zonas", "camaras", "modelos-ia", "sesiones-uso"):
        assert client.get(f"/api/v1/{ruta}/", params={"limit": 501}).status_code == 422, ruta
        assert client.get(f"/api/v1/{ruta}/", params={"limit": 0}).status_code == 422, ruta
        assert client.get(f"/api/v1/{ruta}/", params={"skip": -1}).status_code == 422, ruta
        assert client.get(f"/api/v1/{ruta}/", params={"limit": 500}).status_code == 200, ruta
