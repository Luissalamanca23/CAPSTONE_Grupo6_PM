def _crear_equipo(client, sucursal_id, codigo_activo="EQ-0100"):
    payload = {"sucursal_id": sucursal_id, "codigo_activo": codigo_activo, "nombre": "Eliptica"}
    return client.post("/api/v1/equipamiento/", json=payload).json()


def test_listar_tipos_falla(client):
    respuesta = client.get("/api/v1/incidencias/tipos-falla")
    assert respuesta.status_code == 200
    codigos = {item["codigo"] for item in respuesta.json()}
    assert codigos == {"DESGASTE", "SONIDO_EXTRANO", "ROTA", "NO_ENCIENDE", "MOVIMIENTO_ANOMALO", "OTRO"}


def test_listar_tipos_falla_solo_reporte_qr_excluye_los_de_solo_ia(client):
    respuesta = client.get("/api/v1/incidencias/tipos-falla", params={"solo_reporte_qr": True})
    assert respuesta.status_code == 200
    codigos = {item["codigo"] for item in respuesta.json()}
    # MOVIMIENTO_ANOMALO solo lo detecta la IA (permite_reporte_qr = False en el catalogo).
    assert "MOVIMIENTO_ANOMALO" not in codigos
    assert "ROTA" in codigos


def test_reportar_incidencia_por_qr_autocompleta_descripcion_y_prioridad(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id)
    token = equipo["qr_activo"]["token"]
    payload = {
        "token": token,
        "tipo_falla_codigo": "ROTA",
        "reportado_por": "Socio anonimo",
    }
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    assert respuesta.status_code == 201
    incidencia = respuesta.json()
    assert incidencia["equipo_id"] == equipo["id"]
    assert incidencia["origen"] == "qr"
    assert incidencia["estado"] == "pendiente"
    # "ROTA" se clasifica automaticamente como urgente (prioridad_base del catalogo).
    assert incidencia["prioridad"] == "urgente"
    assert incidencia["descripcion"]  # se autocompleta, no queda vacia
    assert incidencia["tipo_falla"]["codigo"] == "ROTA"


def test_clasificacion_automatica_por_tipo_de_falla(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-0150")
    token = equipo["qr_activo"]["token"]
    casos = {
        "DESGASTE": "baja",
        "SONIDO_EXTRANO": "media",
        "ROTA": "urgente",
        "NO_ENCIENDE": "urgente",
        "OTRO": "media",
    }
    for codigo, prioridad_esperada in casos.items():
        respuesta = client.post(
            "/api/v1/incidencias/reporte-qr",
            json={"token": token, "tipo_falla_codigo": codigo, "reportado_por": "Socio"},
        )
        assert respuesta.status_code == 201
        assert respuesta.json()["prioridad"] == prioridad_esperada


def test_reporte_qr_con_falla_solo_ia_es_rechazado(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-0180")
    token = equipo["qr_activo"]["token"]
    payload = {"token": token, "tipo_falla_codigo": "MOVIMIENTO_ANOMALO", "reportado_por": "Socio"}
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    # MOVIMIENTO_ANOMALO solo lo detecta la IA: el formulario publico no debe aceptarlo.
    assert respuesta.status_code == 400


def test_reporte_qr_token_inexistente_devuelve_404(client):
    payload = {"token": "00000000-0000-0000-0000-000000000000", "tipo_falla_codigo": "OTRO", "reportado_por": "Socio"}
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    assert respuesta.status_code == 404


def test_reporte_qr_sin_nombre_es_rechazado(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-0160")
    token = equipo["qr_activo"]["token"]
    payload = {"token": token, "tipo_falla_codigo": "OTRO", "reportado_por": ""}
    respuesta = client.post("/api/v1/incidencias/reporte-qr", json=payload)
    # El nombre es el unico campo de texto libre y es obligatorio: un string vacio
    # debe ser rechazado por el esquema (422), no aceptado como reporte anonimo.
    assert respuesta.status_code == 422


def test_listar_incidencias_filtrando_por_estado(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-0200")
    client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": equipo["id"], "tipo_falla_codigo": "SONIDO_EXTRANO"},
    )
    listado = client.get("/api/v1/incidencias/", params={"estado": "pendiente"})
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_marcar_incidencia_resuelta_registra_fecha(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-0300")
    creada = client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": equipo["id"], "tipo_falla_codigo": "DESGASTE"},
    ).json()
    assert creada["origen"] == "tecnico"
    respuesta = client.patch(f"/api/v1/incidencias/{creada['id']}", json={"estado": "resuelta"})
    assert respuesta.status_code == 200
    actualizada = respuesta.json()
    assert actualizada["estado"] == "resuelta"
    assert actualizada["fecha_resolucion"] is not None


def test_incidencia_para_equipo_inexistente_devuelve_404(client):
    respuesta = client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": 9999, "tipo_falla_codigo": "OTRO"},
    )
    assert respuesta.status_code == 404


def test_incidencia_con_tipo_falla_inexistente_devuelve_404(client, sucursal_id):
    equipo = _crear_equipo(client, sucursal_id, "EQ-0400")
    respuesta = client.post(
        "/api/v1/incidencias/",
        json={"equipo_id": equipo["id"], "tipo_falla_codigo": "NO_EXISTE"},
    )
    assert respuesta.status_code == 404
