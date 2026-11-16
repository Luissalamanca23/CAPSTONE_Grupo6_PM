"""Mantenimientos (RF-16 y RF-17): registro, validaciones, resolucion de incidencias,
historial por equipo y costos acumulados.

El registro exige tipo (preventivo o correctivo), quien lo hizo y que se hizo; el costo es
opcional pero nunca negativo, y la fecha la pone el servidor.
"""

import pytest

from app.models.gymkeep import EstadoIncidencia, Incidencia

URL = "/api/v1/mantenimientos/"


def _crear_equipo(client, sucursal_id, codigo="EQ-M01"):
    respuesta = client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "codigo_activo": codigo, "nombre": f"Maquina {codigo}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _crear_incidencia(client, equipo_id, tipo_falla="ROTA"):
    respuesta = client.post("/api/v1/incidencias/", json={"equipo_id": equipo_id, "tipo_falla_codigo": tipo_falla})
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _registrar(client, equipo_id, **datos):
    payload = {"equipo_id": equipo_id, "tecnico": "Ana Soto", "descripcion": "Ajuste general"}
    payload.update(datos)
    return client.post(URL, json=payload)


# ---------- registro y validaciones ----------


def test_registrar_un_mantenimiento_guarda_tipo_costo_fecha_y_equipo(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id)
    respuesta = _registrar(client, equipo["id"], tipo="preventivo", costo_total=45000)
    assert respuesta.status_code == 201
    filas = respuesta.json()
    assert len(filas) == 1
    fila = filas[0]
    assert fila["equipo_id"] == equipo["id"]
    assert fila["tipo"] == "preventivo"
    assert fila["tecnico"] == "Ana Soto"
    assert fila["costo_total"] == 45000
    assert fila["incidencia_id"] is None  # preventivo sin falla asociada: un solo registro general
    assert fila["fecha_inicio"]  # la fecha la pone el servidor


def test_sin_indicar_el_tipo_queda_como_correctivo(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id)
    fila = _registrar(client, equipo["id"]).json()[0]
    assert fila["tipo"] == "correctivo"
    assert fila["costo_total"] is None  # el costo es opcional


def test_un_costo_cero_es_valido(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id)
    respuesta = _registrar(client, equipo["id"], costo_total=0)
    assert respuesta.status_code == 201
    assert respuesta.json()[0]["costo_total"] == 0


@pytest.mark.parametrize(
    "cambios",
    [
        {"tecnico": ""},  # quien lo hizo es obligatorio
        {"descripcion": ""},  # que se hizo es obligatorio
        {"tipo": "otro"},  # solo preventivo o correctivo
        {"costo_total": -1},  # el costo no puede ser negativo
    ],
)
def test_datos_invalidos_se_rechazan_y_no_crean_nada(client, sucursal_id, cambios):
    equipo = _crear_equipo(client, sucursal_id)
    respuesta = _registrar(client, equipo["id"], **cambios)
    assert respuesta.status_code == 422
    assert client.get(URL, params={"equipo_id": equipo["id"]}).json() == []


def test_sin_equipo_o_con_equipo_inexistente_se_rechaza(client):
    assert client.post(URL, json={"tecnico": "Ana", "descripcion": "Ajuste"}).status_code == 422
    assert _registrar(client, 9999).status_code == 404


# ---------- incidencias que resuelve el mantenimiento ----------


def test_el_mantenimiento_deja_resueltas_las_incidencias_y_el_costo_se_cuenta_una_sola_vez(
    client, db_session, sucursal_id
):
    equipo = _crear_equipo(client, sucursal_id)
    incidencias = [_crear_incidencia(client, equipo["id"]), _crear_incidencia(client, equipo["id"], "OTRO")]
    ids = [i["id"] for i in incidencias]

    respuesta = _registrar(client, equipo["id"], incidencia_ids=ids, costo_total=30000)
    assert respuesta.status_code == 201
    filas = respuesta.json()
    assert len(filas) == 2  # una fila por incidencia
    assert sorted(f["incidencia_id"] for f in filas) == sorted(ids)
    # Una visita cuesta una sola vez: el costo va en la primera fila y la otra queda vacia.
    assert filas[0]["costo_total"] == 30000
    assert filas[1]["costo_total"] is None

    db_session.expire_all()
    for incidencia_id in ids:
        incidencia = db_session.get(Incidencia, incidencia_id)
        assert incidencia.estado == EstadoIncidencia.resuelta
        assert incidencia.fecha_resolucion is not None


def test_se_ignoran_las_incidencias_de_otro_equipo_o_ya_resueltas(client, db_session, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-M10")
    otro = _crear_equipo(client, sucursal_id, "EQ-M11")
    ajena = _crear_incidencia(client, otro["id"])
    resuelta = _crear_incidencia(client, equipo["id"])
    assert client.patch(f"/api/v1/incidencias/{resuelta['id']}", json={"estado": "resuelta"}).status_code == 200

    respuesta = _registrar(client, equipo["id"], incidencia_ids=[ajena["id"], resuelta["id"]], costo_total=12000)
    assert respuesta.status_code == 201
    filas = respuesta.json()
    # Ninguna es valida: queda un registro general del equipo y el costo no se pierde.
    assert len(filas) == 1
    assert filas[0]["incidencia_id"] is None
    assert filas[0]["costo_total"] == 12000

    db_session.expire_all()
    assert db_session.get(Incidencia, ajena["id"]).estado == EstadoIncidencia.pendiente


def test_registrar_un_mantenimiento_no_cambia_el_estado_del_equipo(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id)
    assert client.patch(f"/api/v1/equipamiento/{equipo['id']}", json={"estado": "en_mantenimiento"}).status_code == 200
    _registrar(client, equipo["id"])
    # El tecnico confirma el estado aparte (PATCH /equipamiento): el registro no lo toca.
    assert client.get(f"/api/v1/equipamiento/{equipo['id']}").json()["estado"] == "en_mantenimiento"


# ---------- historial y costos acumulados (RF-17) ----------


def test_el_historial_de_un_equipo_y_su_total_de_costos_coinciden_con_lo_registrado(client, sucursal_id):
    a = _crear_equipo(client, sucursal_id, "EQ-H01")
    b = _crear_equipo(client, sucursal_id, "EQ-H02")
    for costo in (10000, 25000, 0):
        assert _registrar(client, a["id"], costo_total=costo).status_code == 201
    assert _registrar(client, b["id"], costo_total=99999).status_code == 201

    historial_a = client.get(URL, params={"equipo_id": a["id"]}).json()
    assert len(historial_a) == 3  # el 100 % de las mantenciones del equipo
    assert all(m["equipo_id"] == a["id"] for m in historial_a)
    assert sum(m["costo_total"] or 0 for m in historial_a) == 35000  # diferencia 0

    todo = client.get(URL).json()
    assert len(todo) == 4
    assert sum(m["costo_total"] or 0 for m in todo) == 134999
    assert {m["equipo"]["codigo_activo"] for m in todo} == {"EQ-H01", "EQ-H02"}  # cada fila trae su equipo


def test_el_historial_se_filtra_por_tipo_texto_y_fecha(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id)
    _registrar(client, equipo["id"], tipo="preventivo", tecnico="Luis Mora", descripcion="Lubricacion", costo_total=45000)
    _registrar(client, equipo["id"], tipo="correctivo", tecnico="Ana Soto", descripcion="Cambio de polea", costo_total=38000)

    preventivos = client.get(URL, params={"tipo": "preventivo"}).json()
    assert [m["tecnico"] for m in preventivos] == ["Luis Mora"]

    por_texto = client.get(URL, params={"q": "polea"}).json()
    assert [m["descripcion"] for m in por_texto] == ["Cambio de polea"]

    assert len(client.get(URL, params={"fecha_desde": "2000-01-01"}).json()) == 2
    assert client.get(URL, params={"fecha_desde": "2100-01-01"}).json() == []
    assert client.get(URL, params={"fecha_hasta": "2000-01-01"}).json() == []
