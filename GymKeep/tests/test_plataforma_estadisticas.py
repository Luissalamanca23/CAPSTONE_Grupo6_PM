def test_estadisticas_vacias_traen_todas_las_claves_en_cero(client):
    respuesta = client.get("/api/v1/estadisticas/")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["equipos_total"] == 0
    assert datos["incidencias_abiertas"] == 0
    assert set(datos["equipos_por_estado"]) == {"operativo", "en_mantenimiento", "fuera_de_servicio", "retirado"}
    assert set(datos["incidencias_por_estado"]) == {"pendiente", "en_proceso", "resuelta", "descartada"}
    assert set(datos["incidencias_abiertas_por_prioridad"]) == {"baja", "media", "alta", "urgente"}


def test_estadisticas_cuentan_mas_de_100_registros_sin_truncar(client, sucursal_id):
    primero = None
    for i in range(105):
        equipo = client.post(
            "/api/v1/equipamiento/",
            json={"sucursal_id": sucursal_id, "codigo_activo": f"EQ-S{i:03d}", "nombre": "Equipo"},
        ).json()
        primero = primero or equipo
    client.patch(f"/api/v1/equipamiento/{primero['id']}", json={"estado": "fuera_de_servicio"})

    creadas = []
    for _ in range(3):
        creadas.append(
            client.post(
                "/api/v1/incidencias/", json={"equipo_id": primero["id"], "tipo_falla_codigo": "ROTA"}
            ).json()
        )
    client.patch(f"/api/v1/incidencias/{creadas[0]['id']}", json={"estado": "en_proceso"})
    client.patch(f"/api/v1/incidencias/{creadas[1]['id']}", json={"estado": "resuelta"})

    datos = client.get("/api/v1/estadisticas/").json()
    assert datos["equipos_total"] == 105
    assert datos["equipos_por_estado"]["fuera_de_servicio"] == 1
    assert datos["incidencias_por_estado"] == {"pendiente": 1, "en_proceso": 1, "resuelta": 1, "descartada": 0}
    assert datos["incidencias_abiertas"] == 2
    assert datos["incidencias_abiertas_por_prioridad"]["urgente"] == 2
