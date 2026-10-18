"""Eliminacion desde el panel: maquinas, zonas, camaras, sucursales, reportes y mantenimientos."""

import pytest

from app.models.gymkeep import Camara, Equipo, Incidencia, Mantenimiento, QrEquipo, Sucursal, Zona
from app.services import eliminacion


class ColeccionFalsa:
    def __init__(self):
        self.filtros = []

    def delete_many(self, filtro):
        self.filtros.append(filtro)


class MongoFalso:
    def __init__(self):
        for nombre in ("camaras_vivo", "eventos_ia", "detecciones_raw", "telemetria_camaras", "fotos_equipos"):
            setattr(self, nombre, ColeccionFalsa())


@pytest.fixture()
def mongo(monkeypatch):
    falso = MongoFalso()
    monkeypatch.setattr(eliminacion, "get_mongo_db", lambda: falso)
    return falso


def crear_equipo(client, sucursal_id, codigo="EQ-1", zona_id=None):
    return client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "zona_id": zona_id, "codigo_activo": codigo, "nombre": f"Maquina {codigo}"},
    ).json()


def crear_incidencia(client, equipo_id):
    respuesta = client.post("/api/v1/incidencias/", json={"equipo_id": equipo_id, "tipo_falla_codigo": "OTRO"})
    assert respuesta.status_code == 201
    return respuesta.json()


def test_equipo_con_historial_pide_confirmacion_y_se_borra_en_cascada(client, db_session, sucursal_id, mongo):
    equipo = crear_equipo(client, sucursal_id)
    incidencia = crear_incidencia(client, equipo["id"])
    client.post(
        "/api/v1/mantenimientos/",
        json={"equipo_id": equipo["id"], "tecnico": "Ana", "descripcion": "Cambio de correa", "incidencia_ids": [incidencia["id"]]},
    )

    resumen = client.get(f"/api/v1/equipamiento/{equipo['id']}/resumen-eliminacion").json()
    assert resumen["entidad"] == "maquina"
    assert resumen["conteos"]["incidencias"] == 1
    assert resumen["conteos"]["mantenimientos"] == 1
    assert resumen["conteos"]["codigos_qr"] == 1

    # Sin confirmar no se borra nada.
    assert client.delete(f"/api/v1/equipamiento/{equipo['id']}").status_code == 400
    assert db_session.query(Equipo).count() == 1

    assert client.delete(f"/api/v1/equipamiento/{equipo['id']}?forzar=true").status_code == 204
    db_session.expire_all()
    assert db_session.query(Equipo).count() == 0
    assert db_session.query(Incidencia).count() == 0
    assert db_session.query(Mantenimiento).count() == 0
    assert db_session.query(QrEquipo).count() == 0
    assert mongo.fotos_equipos.filtros == [{"_id": {"$in": [equipo["id"]]}}]


def test_equipo_sin_historial_se_borra_sin_forzar(client, sucursal_id, mongo):
    equipo = crear_equipo(client, sucursal_id)
    assert client.delete(f"/api/v1/equipamiento/{equipo['id']}").status_code == 204
    assert client.get(f"/api/v1/equipamiento/{equipo['id']}").status_code == 404


def test_eliminar_equipo_inexistente_devuelve_404(client):
    assert client.delete("/api/v1/equipamiento/9999").status_code == 404
    assert client.get("/api/v1/equipamiento/9999/resumen-eliminacion").status_code == 404


def test_eliminar_zona_conserva_las_maquinas_sin_zona(client, db_session, sucursal_id, zona_id):
    equipo = crear_equipo(client, sucursal_id, zona_id=zona_id)
    resumen = client.get(f"/api/v1/zonas/{zona_id}/resumen-eliminacion").json()
    assert resumen["conteos"]["maquinas_sin_zona"] == 1

    assert client.delete(f"/api/v1/zonas/{zona_id}").status_code == 204
    db_session.expire_all()
    assert db_session.query(Zona).count() == 0
    conservado = db_session.get(Equipo, equipo["id"])
    assert conservado is not None and conservado.zona_id is None


def test_eliminar_camara_limpia_mongo_y_conserva_reportes(client, db_session, sucursal_id, mongo):
    camara = client.post("/api/v1/camaras/", json={"codigo": "CAM-D", "nombre": "Camara D", "sucursal_id": sucursal_id}).json()
    equipo = crear_equipo(client, sucursal_id)
    incidencia = crear_incidencia(client, equipo["id"])
    db_session.query(Incidencia).filter(Incidencia.id == incidencia["id"]).update({"camara_id": camara["id"]})
    db_session.commit()

    assert client.delete(f"/api/v1/camaras/{camara['id']}?forzar=true").status_code == 204
    db_session.expire_all()
    assert db_session.query(Camara).count() == 0
    assert db_session.get(Incidencia, incidencia["id"]).camara_id is None
    assert mongo.camaras_vivo.filtros == [{"_id": {"$in": [camara["id"]]}}]
    assert client.delete(f"/api/v1/camaras/{camara['id']}").status_code == 404


def test_eliminar_sucursal_borra_todo_lo_suyo(client, db_session, sucursal_id, zona_id, mongo):
    equipo = crear_equipo(client, sucursal_id, zona_id=zona_id)
    crear_incidencia(client, equipo["id"])
    client.post("/api/v1/camaras/", json={"codigo": "CAM-S", "nombre": "Camara S", "sucursal_id": sucursal_id})

    resumen = client.get(f"/api/v1/sucursales/{sucursal_id}/resumen-eliminacion").json()
    assert resumen["conteos"]["maquinas"] == 1
    assert resumen["conteos"]["camaras"] == 1
    assert resumen["conteos"]["incidencias"] == 1
    assert resumen["total_dependientes"] >= 4

    assert client.delete(f"/api/v1/sucursales/{sucursal_id}").status_code == 400
    assert client.delete(f"/api/v1/sucursales/{sucursal_id}?forzar=true").status_code == 204
    db_session.expire_all()
    for modelo in (Sucursal, Zona, Equipo, Camara, Incidencia, QrEquipo):
        assert db_session.query(modelo).count() == 0
    assert client.get("/api/v1/sucursales/").json() == []


def test_eliminar_incidencia_y_mantenimiento(client, db_session, sucursal_id):
    equipo = crear_equipo(client, sucursal_id)
    incidencia = crear_incidencia(client, equipo["id"])
    mant = client.post(
        "/api/v1/mantenimientos/",
        json={"equipo_id": equipo["id"], "tecnico": "Ana", "descripcion": "Ajuste", "incidencia_ids": [incidencia["id"]]},
    ).json()[0]

    assert client.delete(f"/api/v1/incidencias/{incidencia['id']}").status_code == 204
    assert client.delete(f"/api/v1/incidencias/{incidencia['id']}").status_code == 404
    db_session.expire_all()
    # El mantenimiento sobrevive, solo pierde el vinculo con el reporte borrado.
    assert db_session.get(Mantenimiento, mant["id"]).incidencia_id is None

    assert client.delete(f"/api/v1/mantenimientos/{mant['id']}").status_code == 204
    assert client.delete(f"/api/v1/mantenimientos/{mant['id']}").status_code == 404
