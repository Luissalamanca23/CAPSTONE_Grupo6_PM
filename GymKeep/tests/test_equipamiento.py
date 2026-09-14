def test_crear_y_listar_equipo(client, sucursal_id, zona_id):
    payload = {
        "sucursal_id": sucursal_id,
        "zona_id": zona_id,
        "codigo_activo": "EQ-0001",
        "nombre": "Cinta de correr Technogym",
        "marca": "Technogym",
        "modelo": "Run Personal",
    }
    respuesta = client.post("/api/v1/equipamiento/", json=payload)
    assert respuesta.status_code == 201
    creado = respuesta.json()
    assert creado["codigo_activo"] == "EQ-0001"
    assert creado["estado"] == "operativo"
    # Al crear el equipo se le emite automaticamente un QR activo (token UUID).
    assert creado["qr_activo"] is not None
    assert creado["qr_activo"]["activo"] is True

    listado = client.get("/api/v1/equipamiento/")
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_no_permite_codigo_activo_duplicado_en_la_misma_sucursal(client, sucursal_id):
    payload = {"sucursal_id": sucursal_id, "codigo_activo": "EQ-DUP", "nombre": "Bicicleta estatica"}
    assert client.post("/api/v1/equipamiento/", json=payload).status_code == 201
    respuesta_dup = client.post("/api/v1/equipamiento/", json=payload)
    assert respuesta_dup.status_code == 400


def test_crear_equipo_con_sucursal_inexistente_devuelve_404(client):
    payload = {"sucursal_id": 9999, "codigo_activo": "EQ-X", "nombre": "Press de banca"}
    respuesta = client.post("/api/v1/equipamiento/", json=payload)
    assert respuesta.status_code == 404


def test_obtener_equipo_por_qr(client, sucursal_id):
    payload = {"sucursal_id": sucursal_id, "codigo_activo": "EQ-0777", "nombre": "Press de banca"}
    creado = client.post("/api/v1/equipamiento/", json=payload).json()
    token = creado["qr_activo"]["token"]

    respuesta = client.get(f"/api/v1/equipamiento/qr/{token}")
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Press de banca"


def test_obtener_equipo_por_qr_token_invalido_devuelve_404(client):
    respuesta = client.get("/api/v1/equipamiento/qr/no-es-un-uuid")
    assert respuesta.status_code == 404


def test_actualizar_estado_equipo(client, sucursal_id):
    creado = client.post(
        "/api/v1/equipamiento/", json={"sucursal_id": sucursal_id, "codigo_activo": "EQ-0555", "nombre": "Remo"}
    ).json()
    respuesta = client.patch(
        f"/api/v1/equipamiento/{creado['id']}", json={"estado": "en_mantenimiento"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "en_mantenimiento"


def test_equipo_inexistente_devuelve_404(client):
    respuesta = client.get("/api/v1/equipamiento/9999")
    assert respuesta.status_code == 404


def test_generar_codigo_qr_devuelve_imagen_png(client, sucursal_id):
    creado = client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "codigo_activo": "EQ-QRIMG", "nombre": "Sentadilla"},
    ).json()
    respuesta = client.get(f"/api/v1/equipamiento/{creado['id']}/codigo-qr")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"
    assert len(respuesta.content) > 0


def test_generar_codigo_qr_equipo_inexistente_devuelve_404(client):
    respuesta = client.get("/api/v1/equipamiento/9999/codigo-qr")
    assert respuesta.status_code == 404


def test_regenerar_qr_revoca_el_anterior_y_emite_uno_nuevo(client, sucursal_id):
    creado = client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "codigo_activo": "EQ-REGEN", "nombre": "Elíptica"},
    ).json()
    token_original = creado["qr_activo"]["token"]

    respuesta = client.post(f"/api/v1/equipamiento/{creado['id']}/regenerar-qr")
    assert respuesta.status_code == 201
    nuevo = respuesta.json()
    assert nuevo["activo"] is True
    assert nuevo["token"] != token_original

    # El QR anterior ya no resuelve el equipo (fue revocado).
    respuesta_vieja = client.get(f"/api/v1/equipamiento/qr/{token_original}")
    assert respuesta_vieja.status_code == 404

    # El nuevo token si lo resuelve.
    respuesta_nueva = client.get(f"/api/v1/equipamiento/qr/{nuevo['token']}")
    assert respuesta_nueva.status_code == 200


def test_no_se_puede_eliminar_equipo_con_incidencias(client, sucursal_id):
    creado = client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "codigo_activo": "EQ-CONHIST", "nombre": "Banco"},
    ).json()
    client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": creado["id"], "tipo_falla_codigo": "OTRO"},
    )
    respuesta = client.delete(f"/api/v1/equipamiento/{creado['id']}")
    assert respuesta.status_code == 400
