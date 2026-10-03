"""Integracion vision <-> plataforma (/api/v1/vision): zonas, parametros, vivo, uso y fotos."""

import io
import itertools
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from app.models.gymkeep import SesionUso
from app.services import vision_service


class ColeccionFalsa:
    """Lo minimo de pymongo que usa vision_service (filtros por _id, $set, upsert)."""

    _ids = itertools.count(1)

    def __init__(self):
        self.docs = {}

    def find(self, filtro=None, proyeccion=None):
        return [dict(d) for d in self.docs.values()]

    def find_one(self, filtro, proyeccion=None):
        doc = self.docs.get(filtro["_id"])
        return dict(doc) if doc else None

    def insert_one(self, doc):
        doc = {"_id": next(self._ids), **doc}
        self.docs[doc["_id"]] = doc

    def update_one(self, filtro, cambios, upsert=False):
        doc = self.docs.get(filtro["_id"])
        if doc is None:
            if not upsert:
                return
            doc = self.docs[filtro["_id"]] = {"_id": filtro["_id"]}
        doc.update(cambios["$set"])

    def replace_one(self, filtro, doc, upsert=False):
        self.docs[filtro["_id"]] = {"_id": filtro["_id"], **doc}


class MongoFalso:
    def __init__(self):
        for nombre in ("camaras_vivo", "detecciones_raw", "telemetria_camaras", "fotos_equipos"):
            setattr(self, nombre, ColeccionFalsa())


@pytest.fixture()
def mongo(monkeypatch):
    falso = MongoFalso()
    monkeypatch.setattr(vision_service, "get_mongo_db", lambda: falso)
    return falso


@pytest.fixture()
def camara_y_equipo(client, sucursal_id, zona_id):
    equipo = client.post(
        "/api/v1/equipamiento/",
        json={"sucursal_id": sucursal_id, "zona_id": zona_id, "codigo_activo": "EQ-V1", "nombre": "Trotadora 01"},
    ).json()
    camara = client.post(
        "/api/v1/camaras/", json={"codigo": "CAM-V", "nombre": "Camara cardio", "sucursal_id": sucursal_id}
    ).json()
    return camara["id"], equipo["id"]


ZONA = {"puntos": [[0.1, 0.5], [0.4, 0.5], [0.4, 0.9], [0.1, 0.9]]}


def imagen(formato="PNG", tam=(320, 240)):
    salida = io.BytesIO()
    Image.new("RGB", tam, (40, 120, 200)).save(salida, format=formato)
    return salida.getvalue()


def estado_vivo(equipo_id, estado="en_uso", personas=1):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ancho": 1920,
        "alto": 1080,
        "fps_analisis": 5.0,
        "latencia_ms": 12.5,
        "modelo": {"nombre": "gymkeep-usage-detector", "version": "0.1.0"},
        "maquinas": [{"equipo_id": equipo_id, "estado": estado, "sesion_s": 95.0, "personas": personas}],
        "personas": [{"caja": [0.2, 0.3, 0.3, 0.8], "confianza": 0.9, "track_id": 7, "equipo_id": equipo_id}]
        * personas,
    }


# ---------------------------------------------------------------- zonas y parametros


def test_dibujar_editar_y_quitar_la_zona_de_una_maquina(client, mongo, camara_y_equipo):
    camara_id, equipo_id = camara_y_equipo
    url = f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}"

    creada = client.put(url, json=ZONA)
    assert creada.status_code == 200
    assert creada.json()["roi"] == ZONA["puntos"]

    nueva = {"puntos": [[0.2, 0.2], [0.5, 0.2], [0.5, 0.6]]}
    assert client.put(url, json=nueva).json()["roi"] == nueva["puntos"]

    detalle = client.get(f"/api/v1/vision/camaras/{camara_id}").json()
    assert [m["equipo_id"] for m in detalle["lista_maquinas"]] == [equipo_id]
    assert detalle["maquinas"] == 1

    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404
    assert client.get(f"/api/v1/vision/camaras/{camara_id}").json()["lista_maquinas"] == []


def test_zona_invalida_se_rechaza(client, mongo, camara_y_equipo):
    camara_id, equipo_id = camara_y_equipo
    url = f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}"
    assert client.put(url, json={"puntos": [[0.1, 0.1], [1.5, 0.1], [0.5, 0.5]]}).status_code == 422
    assert client.put(url, json={"puntos": [[0.1, 0.1], [0.2, 0.2]]}).status_code == 422


def test_maquina_de_otra_sucursal_no_entra_en_la_camara(client, mongo, camara_y_equipo, db_session):
    camara_id, _ = camara_y_equipo
    empresa_id = client.get("/api/v1/empresas/").json()[0]["id"]
    otra = client.post("/api/v1/sucursales/", json={"empresa_id": empresa_id, "codigo": "PM-02", "nombre": "Otra"}).json()
    equipo = client.post(
        "/api/v1/equipamiento/", json={"sucursal_id": otra["id"], "codigo_activo": "EQ-X", "nombre": "Bici"}
    ).json()
    respuesta = client.put(f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo['id']}", json=ZONA)
    assert respuesta.status_code == 400


def test_parametros_por_camara(client, mongo, camara_y_equipo):
    camara_id, _ = camara_y_equipo
    base = client.get(f"/api/v1/vision/camaras/{camara_id}").json()["parametros"]
    assert base["t_on_s"] == 30 and base["confianza_min"] == 0.5  # valores iniciales del estudio

    calibrados = {"t_on_s": 30, "t_off_s": 90, "confianza_min": 0.25, "gracia_s": 10, "escala_tiempo": 1.0}
    assert client.put(f"/api/v1/vision/camaras/{camara_id}/parametros", json=calibrados).status_code == 200
    assert client.get(f"/api/v1/vision/camaras/{camara_id}").json()["parametros"]["confianza_min"] == 0.25

    invalidos = {**calibrados, "t_off_s": 5}  # T_off debe superar la gracia
    assert client.put(f"/api/v1/vision/camaras/{camara_id}/parametros", json=invalidos).status_code == 422


def test_configuracion_para_el_pipeline_solo_trae_maquinas_con_zona(client, mongo, camara_y_equipo, sucursal_id):
    camara_id, equipo_id = camara_y_equipo
    sin_zona = client.post(
        "/api/v1/equipamiento/", json={"sucursal_id": sucursal_id, "codigo_activo": "EQ-V2", "nombre": "Remo"}
    ).json()
    client.put(f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}", json=ZONA)
    config = client.get(f"/api/v1/vision/camaras/{camara_id}/configuracion").json()
    assert config["codigo"] == "CAM-V"
    assert [m["equipo_id"] for m in config["maquinas"]] == [equipo_id]
    assert sin_zona["id"] not in [m["equipo_id"] for m in config["maquinas"]]


# ---------------------------------------------------------------- en vivo


def test_estado_en_vivo_queda_en_mongo_y_marca_la_camara_en_linea(client, mongo, camara_y_equipo):
    camara_id, equipo_id = camara_y_equipo
    assert client.get(f"/api/v1/vision/camaras/{camara_id}/vivo").json()["en_linea"] is False

    assert client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id)).status_code == 202
    vivo = client.get(f"/api/v1/vision/camaras/{camara_id}/vivo").json()
    assert vivo["en_linea"] is True
    assert vivo["maquinas"][0]["estado"] == "en_uso"
    assert vivo["personas"][0]["track_id"] == 7

    assert len(mongo.detecciones_raw.docs) == 1  # hubo personas
    assert len(mongo.telemetria_camaras.docs) == 1

    # Un segundo envio inmediato: se registra la deteccion, pero la telemetria va cada 30 s.
    client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id))
    assert len(mongo.detecciones_raw.docs) == 2
    assert len(mongo.telemetria_camaras.docs) == 1

    # Sin personas no se llena detecciones_raw.
    client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id, "libre", personas=0))
    assert len(mongo.detecciones_raw.docs) == 2

    camara = client.get("/api/v1/vision/camaras").json()[0]
    assert camara["en_linea"] is True
    assert camara["ultima_conexion"] is not None
    assert (camara["ancho_px"], camara["alto_px"]) == (1920, 1080)


def test_camara_sin_datos_recientes_queda_sin_senal(client, mongo, camara_y_equipo):
    camara_id, equipo_id = camara_y_equipo
    client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id))
    mongo.camaras_vivo.docs[camara_id]["recibido"] = datetime.now(timezone.utc) - timedelta(seconds=60)
    assert client.get(f"/api/v1/vision/camaras/{camara_id}/vivo").json()["en_linea"] is False


def test_cuadro_de_la_camara(client, mongo, camara_y_equipo):
    camara_id, _ = camara_y_equipo
    url = f"/api/v1/vision/camaras/{camara_id}/cuadro"
    assert client.get(url).status_code == 404

    subida = client.put(url, content=imagen("PNG", (2560, 1440)), headers={"Content-Type": "image/png"})
    assert subida.status_code == 201
    assert subida.json()["ancho"] == 1280  # se achica para no llenar Mongo

    respuesta = client.get(url)
    assert respuesta.headers["content-type"] == "image/jpeg"
    assert respuesta.content[:2] == b"\xff\xd8"
    assert client.get("/api/v1/vision/camaras").json()[0]["tiene_cuadro"] is True

    assert client.put(url, content=b"no es una imagen").status_code == 400


# ---------------------------------------------------------------- uso de maquinas y fotos


def agregar_sesion(db_session, equipo_id, inicio, minutos):
    db_session.add(
        SesionUso(
            equipo_id=equipo_id,
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(minutes=minutos),
            duracion_segundos=minutos * 60,
            estado="cerrada",
            cantidad_eventos=2,
        )
    )
    db_session.commit()


def test_listado_de_maquinas_con_horas_y_estado_en_vivo(client, mongo, camara_y_equipo, db_session):
    camara_id, equipo_id = camara_y_equipo
    ahora = datetime.now(timezone.utc)
    agregar_sesion(db_session, equipo_id, ahora - timedelta(days=10), 60)
    agregar_sesion(db_session, equipo_id, ahora - timedelta(days=1), 30)

    maquina = client.get("/api/v1/vision/maquinas").json()[0]
    assert maquina["horas_uso"] == pytest.approx(1.5, abs=0.01)
    assert maquina["horas_ultimos_7_dias"] == pytest.approx(0.5, abs=0.01)
    assert maquina["sesiones"] == 2
    assert maquina["medido_por_camara"] is False
    assert maquina["en_uso_ahora"] is None  # ninguna camara la mira
    assert maquina["horas_desde_mantencion"] is None

    client.put(f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}", json=ZONA)
    client.post(f"/api/v1/vision/camaras/{camara_id}/vivo", json=estado_vivo(equipo_id))
    maquina = client.get("/api/v1/vision/maquinas").json()[0]
    assert maquina["medido_por_camara"] is True
    assert maquina["camaras"][0]["codigo"] == "CAM-V"
    assert maquina["en_uso_ahora"] is True
    assert maquina["estado_vivo"]["sesion_s"] == 95.0


def test_horas_desde_la_ultima_mantencion(client, mongo, camara_y_equipo, db_session):
    _, equipo_id = camara_y_equipo
    ahora = datetime.now(timezone.utc)
    agregar_sesion(db_session, equipo_id, ahora - timedelta(days=10), 60)
    client.post(
        "/api/v1/mantenimientos/",
        json={"equipo_id": equipo_id, "tipo": "preventivo", "tecnico": "Ana", "descripcion": "Revision"},
    )
    agregar_sesion(db_session, equipo_id, ahora + timedelta(minutes=1), 30)
    maquina = client.get("/api/v1/vision/maquinas").json()[0]
    assert maquina["horas_desde_mantencion"] == pytest.approx(0.5, abs=0.01)
    assert maquina["ultima_mantencion"] is not None


def test_detalle_trae_todo_el_historial(client, mongo, camara_y_equipo, db_session):
    _, equipo_id = camara_y_equipo
    agregar_sesion(db_session, equipo_id, datetime.now(timezone.utc) - timedelta(hours=3), 45)
    client.post(
        "/api/v1/mantenimientos/",
        json={"equipo_id": equipo_id, "tipo": "correctivo", "tecnico": "Ana", "descripcion": "Cambio de correa",
              "costo_total": 35000},
    )
    detalle = client.get(f"/api/v1/vision/maquinas/{equipo_id}").json()
    assert detalle["resumen"]["horas_uso"] == pytest.approx(0.75, abs=0.01)
    assert len(detalle["uso_diario"]) == 30
    assert sum(d["sesiones"] for d in detalle["uso_diario"]) == 1
    assert len(detalle["sesiones"]) == 1
    assert detalle["mantenciones"][0]["costo_total"] == 35000
    assert client.get("/api/v1/vision/maquinas/9999").status_code == 404


def test_foto_subida_y_desde_la_camara(client, mongo, camara_y_equipo):
    camara_id, equipo_id = camara_y_equipo
    url = f"/api/v1/vision/maquinas/{equipo_id}/foto"
    assert client.get(url).status_code == 404

    # Sin imagen de la camara no hay de donde recortar.
    client.put(f"/api/v1/vision/camaras/{camara_id}/maquinas/{equipo_id}", json=ZONA)
    assert client.post(f"{url}/desde-camara").status_code == 409

    client.put(f"/api/v1/vision/camaras/{camara_id}/cuadro", content=imagen("JPEG", (1280, 720)))
    recorte = client.post(f"{url}/desde-camara")
    assert recorte.status_code == 201
    assert recorte.json()["origen"] == "camara"
    assert client.get(url).content[:2] == b"\xff\xd8"
    assert client.get("/api/v1/vision/maquinas").json()[0]["tiene_foto"] is True

    assert client.put(url, content=imagen("PNG")).json()["origen"] == "subida"
