def _crear_equipo(client, codigo_qr="QR-100"):
    payload = {"codigo_qr": codigo_qr, "nombre": "Eliptica"}
    return client.post("/api/v1/equipamiento/", json=payload).json()


def test_listar_tipos_falla(client):
    respuesta = client.get("/api/v1/incidencias/tipos-falla")
    assert respuesta.status_code == 200
    valores = {item["valor"] for item in respuesta.json()}
    assert valores == {"desgaste", "sonido_extrano", "rota", "no_enciende", "otro"}


def test_reportar_incidencia_por_qr_autocompleta_descripcion_y_prioridad(client):
    equipo = _crear_equipo(client)
    payload = {
        "codigo_qr": equipo["codigo_qr"],
        "tipo_falla": "rota",
        "reportado_por": "Socio anonimo",
    }
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    assert respuesta.status_code == 201
    incidencia = respuesta.json()
    assert incidencia["equipo_id"] == equipo["id"]
    assert incidencia["estado"] == "pendiente"
    # "rota" se clasifica automaticamente como urgente.
    assert incidencia["prioridad"] == "urgente"
    assert incidencia["descripcion"]  # se autocompleta, no queda vacia


def test_clasificacion_automatica_por_tipo_de_falla(client):
    equipo = _crear_equipo(client, "QR-150")
    casos = {
        "desgaste": "baja",
        "sonido_extrano": "media",
        "rota": "urgente",
        "no_enciende": "urgente",
        "otro": "media",
    }
    for tipo_falla, prioridad_esperada in casos.items():
        respuesta = client.post(
            "/api/v1/incidencias/reporte-qr",
            json={"codigo_qr": equipo["codigo_qr"], "tipo_falla": tipo_falla, "reportado_por": "Socio"},
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["prioridad"] == prioridad_esperada


def test_reporte_qr_inexistente_devuelve_404(client):
    payload = {"codigo_qr": "QR-NO-EXISTE", "tipo_falla": "otro", "reportado_por": "Socio"}
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    assert respuesta.status_code == 404


def test_reporte_qr_sin_nombre_es_rechazado(client):
    equipo = _crear_equipo(client, "QR-160")
    payload = {"codigo_qr": equipo["codigo_qr"], "tipo_falla": "otro", "reportado_por": ""}
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    # El nombre es el unico campo de texto libre y es obligatorio: un string vacio
    # debe ser rechazado por el esquema (422), no aceptado como reporte anonimo.
    assert respuesta.status_code == 422


def test_listar_incidencias_filtrando_por_estado(client):
    equipo = _crear_equipo(client, "QR-200")
    client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": equipo["id"], "tipo_falla": "sonido_extrano"},
    )
    listado = client.get("/api/v1/incidencias/", params={"estado": "pendiente"})
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_marcar_incidencia_resuelta_registra_fecha(client):
    equipo = _crear_equipo(client, "QR-300")
    creada = client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": equipo["id"], "tipo_falla": "desgaste"},
    ).json()
    respuesta = client.patch(f"/api/v1/incidencias/{creada['id']}", json={"estado": "resuelta"})
    assert respuesta.status_code == 200
    actualizada = respuesta.json()
    assert actualizada["estado"] == "resuelta"
    assert actualizada["fecha_resolucion"] is not None


def test_incidencia_para_equipo_inexistente_devuelve_404(client):
    respuesta = client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": 9999, "tipo_falla": "otro"},
    )
    assert respuesta.status_code == 404
