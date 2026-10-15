"""Watchdog de sesiones huerfanas, carreras en la consolidacion y consultas del panel."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.models.gymkeep import SesionUso
from app.schemas.ai_event import EventoIACreate
from app.services import ai_event_service
from tests.conftest import engine
from tests.test_eventos_ia import equipo_y_camara, evento, mongo  # noqa: F401 (fixtures)
from tests.test_vision_api import ZONA, estado_vivo
from tests.test_vision_api import mongo as mongo_vision  # noqa: F401 (fixture)

INICIO = "2026-09-26T18:00:00-03:00"
EN_5_MIN = "2026-09-26T18:05:00-03:00"


@pytest.fixture()
def indice_unico(db_session):
    """Indice parcial de postgres/schema.sql (tambien declarado en el modelo SesionUso)."""
    db_session.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS ux_sesiones_uso_abierta ON sesiones_uso(equipo_id, camara_id) WHERE estado = 'abierta'")
    )
    db_session.commit()


def post(client, *args, **kwargs):
    respuesta = client.post("/api/v1/eventos-ia/", json=evento(*args, **kwargs))
    assert respuesta.status_code == 201
    return respuesta.json()


def estados(db_session):
    db_session.expire_all()
    return sorted(s.estado for s in db_session.query(SesionUso))


# ---------------------------------------------------------------- watchdog


def test_watchdog_cierra_en_el_ultimo_evento_la_sesion_sin_latidos(client, mongo, equipo_y_camara, db_session):
    equipo_id, camara_id = equipo_y_camara
    post(client, "inicio_uso", INICIO, equipo_id, camara_id)
    post(client, "uso_en_curso", EN_5_MIN, equipo_id, camara_id)

    ahora = datetime.now(timezone.utc)
    assert ai_event_service.cerrar_sesiones_huerfanas(db_session, ahora=ahora) == 0  # recien llegaron
    assert estados(db_session) == ["abierta"]

    futuro = ahora + timedelta(seconds=ai_event_service.UMBRAL_HUERFANA_S + 5)
    assert ai_event_service.cerrar_sesiones_huerfanas(db_session, ahora=futuro) == 1
    sesion = db_session.query(SesionUso).one()
    assert sesion.estado == "cerrada"
    assert sesion.duracion_segundos == 300  # hasta el ultimo evento, no hasta "ahora"
    assert sesion.metadata_json["cierre"] == "watchdog"
    assert ai_event_service.cerrar_sesiones_huerfanas(db_session, ahora=futuro) == 0


def test_watchdog_descarta_la_sesion_que_solo_tuvo_inicio(client, mongo, equipo_y_camara, db_session):
    equipo_id, camara_id = equipo_y_camara
    post(client, "inicio_uso", INICIO, equipo_id, camara_id)
    futuro = datetime.now(timezone.utc) + timedelta(hours=1)
    assert ai_event_service.cerrar_sesiones_huerfanas(db_session, ahora=futuro) == 1
    sesion = db_session.query(SesionUso).one()
    assert sesion.estado == "descartada"
    assert sesion.metadata_json["motivo"] == "sin_evidencia_de_continuidad"
    assert sesion.fecha_fin is None  # no se imputa uso no observado


def test_watchdog_no_toca_sesiones_ya_cerradas(client, mongo, equipo_y_camara, db_session):
    equipo_id, camara_id = equipo_y_camara
    post(client, "inicio_uso", INICIO, equipo_id, camara_id)
    post(client, "fin_uso", EN_5_MIN, equipo_id, camara_id)
    assert ai_event_service.cerrar_sesiones_huerfanas(db_session, ahora=datetime.now(timezone.utc) + timedelta(days=1)) == 0
    assert estados(db_session) == ["cerrada"]


def test_la_tarea_del_watchdog_se_puede_desactivar(monkeypatch):
    from app.core import watchdog
    from app.core.config import settings

    monkeypatch.setattr(settings, "vision_watchdog_s", 0)
    assert watchdog.iniciar() is None


# ---------------------------------------------------------------- carreras e integridad


def test_dos_solicitudes_con_el_mismo_evento_devuelven_el_existente(client, mongo, equipo_y_camara, db_session, monkeypatch):
    equipo_id, camara_id = equipo_y_camara
    payload = evento("inicio_uso", INICIO, equipo_id, camara_id)
    primero = client.post("/api/v1/eventos-ia/", json=payload).json()

    # La segunda solicitud ya paso la comprobacion de "existe" cuando la primera confirmo.
    llamadas = iter([None])
    original = ai_event_service._buscar_resumen
    monkeypatch.setattr(
        ai_event_service, "_buscar_resumen", lambda db, uuid: next(llamadas, None) or original(db, uuid)
    )
    segundo = ai_event_service.guardar_evento_ia(db_session, EventoIACreate(**payload))

    assert segundo.id == primero["id"]
    assert estados(db_session) == ["abierta"]  # el rollback deshizo lo que el duplicado alcanzo a tocar


def test_fin_con_fecha_anterior_al_inicio_no_viola_el_orden_de_fechas(client, mongo, equipo_y_camara, db_session):
    equipo_id, camara_id = equipo_y_camara
    post(client, "inicio_uso", INICIO, equipo_id, camara_id)
    post(client, "fin_uso", "2026-09-26T17:59:00-03:00", equipo_id, camara_id)
    sesion = db_session.query(SesionUso).one()
    assert sesion.estado == "cerrada"
    assert sesion.duracion_segundos == 0
    assert ai_event_service._no_antes_de(sesion.fecha_fin, sesion.fecha_inicio) == sesion.fecha_fin


def test_el_indice_impide_dos_sesiones_abiertas_de_la_misma_maquina(
    client, mongo, equipo_y_camara, db_session, indice_unico
):
    equipo_id, camara_id = equipo_y_camara
    post(client, "inicio_uso", INICIO, equipo_id, camara_id)
    db_session.add(
        SesionUso(equipo_id=equipo_id, camara_id=camara_id, fecha_inicio=datetime.now(timezone.utc), estado="abierta")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    # Cerradas o descartadas no cuentan: solo hay una restriccion sobre las abiertas.
    db_session.add(
        SesionUso(equipo_id=equipo_id, camara_id=camara_id, fecha_inicio=datetime.now(timezone.utc), estado="cerrada")
    )
    db_session.commit()


def test_dos_inicios_simultaneos_dejan_una_sola_sesion_abierta(
    client, mongo, equipo_y_camara, db_session, indice_unico, monkeypatch
):
    equipo_id, camara_id = equipo_y_camara
    post(client, "inicio_uso", INICIO, equipo_id, camara_id)

    # El segundo inicio no vio la sesion abierta por el primero (consulta anterior a su commit).
    llamadas = iter([None])
    original = ai_event_service._sesion_abierta
    monkeypatch.setattr(
        ai_event_service, "_sesion_abierta", lambda db, e, c: next(llamadas, None) or original(db, e, c)
    )
    respuesta = client.post("/api/v1/eventos-ia/", json=evento("inicio_uso", EN_5_MIN, equipo_id, camara_id))

    assert respuesta.status_code == 201
    assert respuesta.json()["sesion_uso_id"] is not None
    assert estados(db_session) == ["abierta", "descartada"]


# ---------------------------------------------------------------- consultas del panel


def contar_consultas(llamada):
    cuenta = []

    def contar(conn, cursor, statement, *args):
        cuenta.append(statement)

    event.listen(engine, "before_cursor_execute", contar)
    try:
        llamada()
    finally:
        event.remove(engine, "before_cursor_execute", contar)
    return len(cuenta)


def crear_maquinas_y_camaras(client, sucursal_id, zona_id, n):
    equipos = []
    for i in range(n):
        equipo = client.post(
            "/api/v1/equipamiento/",
            json={"sucursal_id": sucursal_id, "zona_id": zona_id, "codigo_activo": f"EQ-P{i}", "nombre": f"Maquina {i}"},
        ).json()
        camara = client.post(
            "/api/v1/camaras/", json={"codigo": f"CAM-P{i}", "nombre": f"Camara {i}", "sucursal_id": sucursal_id}
        ).json()
        client.put(f"/api/v1/vision/camaras/{camara['id']}/maquinas/{equipo['id']}", json=ZONA)
        equipos.append(equipo["id"])
    return equipos


def test_los_listados_no_hacen_consultas_por_cada_maquina_o_camara(
    client, mongo_vision, sucursal_id, zona_id, db_session
):
    crear_maquinas_y_camaras(client, sucursal_id, zona_id, 2)
    db_session.expire_all()
    pocas = contar_consultas(lambda: (client.get("/api/v1/vision/maquinas"), client.get("/api/v1/vision/camaras")))

    crear_maquinas_y_camaras_extra(client, sucursal_id, zona_id)
    db_session.expire_all()
    muchas = contar_consultas(lambda: (client.get("/api/v1/vision/maquinas"), client.get("/api/v1/vision/camaras")))
    assert muchas == pocas


def crear_maquinas_y_camaras_extra(client, sucursal_id, zona_id):
    for i in range(10, 16):
        equipo = client.post(
            "/api/v1/equipamiento/",
            json={"sucursal_id": sucursal_id, "zona_id": zona_id, "codigo_activo": f"EQ-P{i}", "nombre": f"Maquina {i}"},
        ).json()
        camara = client.post(
            "/api/v1/camaras/", json={"codigo": f"CAM-P{i}", "nombre": f"Camara {i}", "sucursal_id": sucursal_id}
        ).json()
        client.put(f"/api/v1/vision/camaras/{camara['id']}/maquinas/{equipo['id']}", json=ZONA)


def test_la_foto_solo_se_consulta_para_las_maquinas_listadas(client, mongo_vision, sucursal_id, zona_id):
    ids = crear_maquinas_y_camaras(client, sucursal_id, zona_id, 2)
    mongo_vision.fotos_equipos.docs[ids[0]] = {"_id": ids[0], "imagen": b"x"}
    mongo_vision.fotos_equipos.docs[9999] = {"_id": 9999, "imagen": b"x"}  # de una maquina que no se lista
    con_foto = {m["equipo_id"]: m["tiene_foto"] for m in client.get("/api/v1/vision/maquinas").json()}
    assert con_foto == {ids[0]: True, ids[1]: False}


def test_el_detalle_cuenta_incidencias_abiertas_y_acota_el_historial(
    client, mongo_vision, sucursal_id, zona_id, db_session
):
    (equipo_id,) = crear_maquinas_y_camaras(client, sucursal_id, zona_id, 1)
    ahora = datetime.now(timezone.utc)
    for dias, minutos in [(40, 30), (2, 20), (0, 10)]:
        db_session.add(
            SesionUso(
                equipo_id=equipo_id,
                fecha_inicio=ahora - timedelta(days=dias, hours=1),
                fecha_fin=ahora - timedelta(days=dias, hours=1) + timedelta(minutes=minutos),
                duracion_segundos=minutos * 60,
                estado="cerrada",
            )
        )
    db_session.commit()

    detalle = client.get(f"/api/v1/vision/maquinas/{equipo_id}").json()
    assert detalle["resumen"]["sesiones"] == 3
    assert detalle["resumen"]["horas_uso"] == pytest.approx(1.0, abs=0.01)
    assert sum(d["sesiones"] for d in detalle["uso_diario"]) == 2  # la de hace 40 dias queda fuera de los 30
    assert [s["duracion_segundos"] for s in detalle["sesiones"]] == [600, 1200, 1800]  # la mas reciente primero
    assert detalle["resumen"]["incidencias_abiertas"] == 0
