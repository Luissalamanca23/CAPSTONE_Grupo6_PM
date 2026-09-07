def test_crear_y_listar_equipo(client):
    payload = {
        "codigo_qr": "QR-001",
        "nombre": "Cinta de correr Technogym",
        "marca": "Technogym",
        "modelo": "Run Personal",
        "ubicacion": "Sala cardio 1",
    }
    respuesta = client.post("/api/v1/equipamiento/", json=payload)
    assert respuesta.status_code == 201
    creado = respuesta.json()
    assert creado["codigo_qr"] == "QR-001"
    assert creado["estado"] == "operativo"

    listado = client.get("/api/v1/equipamiento/")
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_no_permite_qr_duplicado(client):
    payload = {"codigo_qr": "QR-DUP", "nombre": "Bicicleta estatica"}
    assert client.post("/api/v1/equipamiento/", json=payload).status_code == 201
    respuesta_dup = client.post("/api/v1/equipamiento/", json=payload)
    assert respuesta_dup.status_code == 400


def test_obtener_equipo_por_qr(client):
    payload = {"codigo_qr": "QR-777", "nombre": "Press de banca"}
    client.post("/api/v1/equipamiento/", json=payload)
    respuesta = client.get("/api/v1/equipamiento/qr/QR-777")
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Press de banca"


def test_actualizar_estado_equipo(client):
    creado = client.post(
        "/api/v1/equipamiento/", json={"codigo_qr": "QR-555", "nombre": "Remo"}
    ).json()
    respuesta = client.patch(
        f"/api/v1/equipamiento/{creado['id']}", json={"estado": "en_mantenimiento"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "en_mantenimiento"


def test_equipo_inexistente_devuelve_404(client):
    respuesta = client.get("/api/v1/equipamiento/9999")
    assert respuesta.status_code == 404


def test_generar_codigo_qr_devuelve_imagen_png(client):
    creado = client.post(
        "/api/v1/equipamiento/", json={"codigo_qr": "QR-QRIMG", "nombre": "Sentadilla"}
    ).json()
    respuesta = client.get(f"/api/v1/equipamiento/{creado['id']}/codigo-qr")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "image/png"
    assert len(respuesta.content) > 0


def test_generar_codigo_qr_equipo_inexistente_devuelve_404(client):
    respuesta = client.get("/api/v1/equipamiento/9999/codigo-qr")
    assert respuesta.status_code == 404
