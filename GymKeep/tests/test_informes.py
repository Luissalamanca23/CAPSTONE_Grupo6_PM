"""Informe de funcionamiento de las maquinas (mensual, trimestral y anual) y su Excel."""

from datetime import date, datetime, timezone

import pytest

from app.api.v1 import incidencias as api_incidencias
from app.services import informe_filas as filas
from app.services import informe_periodos as periodos


# ---------------------------------------------------------------- periodos (logica pura)
def test_rangos_de_cada_periodo():
    assert periodos.rango_periodo("mensual", 2026, mes=2) == (date(2026, 2, 1), date(2026, 2, 28))
    assert periodos.rango_periodo("mensual", 2028, mes=2) == (date(2028, 2, 1), date(2028, 2, 29))
    assert periodos.rango_periodo("trimestral", 2026, trimestre=4) == (date(2026, 10, 1), date(2026, 12, 31))
    assert periodos.rango_periodo("anual", 2026) == (date(2026, 1, 1), date(2026, 12, 31))


def test_cantidad_de_meses_por_periodo():
    assert len(periodos.meses_del_periodo("mensual", 2026, mes=5)) == 1
    assert len(periodos.meses_del_periodo("trimestral", 2026, trimestre=1)) == 3
    assert len(periodos.meses_del_periodo("anual", 2026)) == 12


@pytest.mark.parametrize(
    "args",
    [("semanal", 2026, 1, None), ("mensual", 2026, None, None), ("mensual", 2026, 13, None), ("trimestral", 2026, None, 5)],
)
def test_periodos_invalidos_se_rechazan(args):
    tipo, anio, mes, trimestre = args
    with pytest.raises(ValueError):
        periodos.meses_del_periodo(tipo, anio, mes, trimestre)


def test_el_periodo_por_defecto_es_el_ultimo_completo():
    assert periodos.periodo_por_defecto("mensual", date(2026, 11, 12)) == {"anio": 2026, "mes": 10}
    assert periodos.periodo_por_defecto("mensual", date(2026, 1, 5)) == {"anio": 2025, "mes": 12}
    assert periodos.periodo_por_defecto("trimestral", date(2026, 11, 12)) == {"anio": 2026, "trimestre": 3}
    assert periodos.periodo_por_defecto("trimestral", date(2026, 2, 1)) == {"anio": 2025, "trimestre": 4}
    assert periodos.periodo_por_defecto("anual", date(2026, 11, 12)) == {"anio": 2025}


def test_la_fecha_se_mide_en_hora_de_chile():
    # 1 de noviembre 02:00 UTC = 31 de octubre 23:00 en Chile (UTC-3 en verano austral).
    assert periodos.a_fecha_local(datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc)) == date(2026, 10, 31)


# ---------------------------------------------------------------- texto y estado de cada fila
def _inc(dia, prioridad="media", estado="pendiente", cierre=None, tipo="Sonido extraño"):
    return {"fecha": dia, "tipo": tipo, "prioridad": prioridad, "estado": estado, "fecha_cierre": cierre}


def test_sin_incidencias_ni_mantenimientos():
    assert filas.texto_incidencias([]) == "Sin incidencias"
    assert filas.texto_mantenimientos([]) == "Sin mantenimientos"


def test_resumen_de_incidencias_y_mantenimientos():
    texto = filas.texto_incidencias([_inc(date(2026, 10, 3), "urgente", "resuelta", date(2026, 10, 4), "No enciende")])
    assert texto.startswith("1 incidencia:") and "03-10" in texto and "urgente" in texto and "resuelta" in texto
    mant = filas.texto_mantenimientos(
        [{"fecha": date(2026, 10, 5), "tipo": "inspeccion"}, {"fecha": date(2026, 10, 20), "tipo": "preventivo"}]
    )
    assert "1 inspección (05-10)" in mant and "1 preventivo (20-10)" in mant


def test_incidencia_abierta_al_cierre_del_mes():
    fin = date(2026, 10, 31)
    abierta = _inc(date(2026, 9, 10))
    resuelta_antes = _inc(date(2026, 9, 10), estado="resuelta", cierre=date(2026, 10, 2))
    resuelta_despues = _inc(date(2026, 10, 10), estado="resuelta", cierre=date(2026, 11, 3))
    futura = _inc(date(2026, 11, 2))
    assert filas.abiertas_al_cierre([abierta, resuelta_antes, resuelta_despues, futura], fin) == [abierta, resuelta_despues]


def test_estado_del_mes():
    base = dict(estado_actual="operativo", es_mes_en_curso=False)
    assert filas.estado_del_mes(abiertas_cierre=[], **base) == "Operativo"
    assert filas.estado_del_mes(abiertas_cierre=[_inc(date(2026, 10, 1))], **base) == "Operativo con incidencias abiertas"
    assert filas.estado_del_mes(abiertas_cierre=[_inc(date(2026, 10, 1), "urgente")], **base) == "Fuera de servicio"
    assert filas.estado_del_mes(abiertas_cierre=[], en_mantenimiento_al_cierre=True, **base) == "En mantenimiento"
    # El mes en curso usa el estado real de hoy.
    assert filas.estado_del_mes(estado_actual="fuera_de_servicio", es_mes_en_curso=True, abiertas_cierre=[]) == "Fuera de servicio"


def test_observaciones_mencionan_el_uso():
    texto = filas.texto_observaciones(horas_uso=85.4, dias_con_uso=24, del_mes_incidencias=0, observacion_equipo=None)
    assert "85 h" in texto and "24 días" in texto and "Sin fallas" in texto
    assert "Sin uso registrado" in filas.texto_observaciones(
        horas_uso=0, dias_con_uso=0, del_mes_incidencias=0, observacion_equipo=None
    )


# ---------------------------------------------------------------- API
def _crear_equipo(client, sucursal_id, codigo):
    return client.post(
        "/api/v1/equipamiento/", json={"sucursal_id": sucursal_id, "codigo_activo": codigo, "nombre": f"Cinta {codigo}"}
    ).json()


def _mes_actual():
    hoy = periodos.hoy_local()
    return hoy.year, hoy.month


def test_el_informe_exige_sesion(client_anonimo):
    assert client_anonimo.get("/api/v1/informes/borrador").status_code == 401
    assert client_anonimo.post("/api/v1/informes/excel", json={"gimnasio": "X"}).status_code == 401


def test_borrador_mensual_con_maquinas_sin_fallas(client, sucursal_id):
    _crear_equipo(client, sucursal_id, "EQ-I1")
    _crear_equipo(client, sucursal_id, "EQ-I2")
    anio, mes = _mes_actual()
    r = client.get("/api/v1/informes/borrador", params={"tipo": "mensual", "anio": anio, "mes": mes})
    assert r.status_code == 200
    datos = r.json()
    assert datos["tipo"] == "mensual" and len(datos["filas"]) == 2
    assert datos["gimnasio"] and datos["responsable"]  # el responsable propuesto es quien inicio sesion
    fila = datos["filas"][0]
    assert fila["incidencias"] == "Sin incidencias" and fila["mantenimientos"] == "Sin mantenimientos"
    assert fila["estado"] == "Operativo"
    assert set(fila) >= {"fecha", "codigo", "maquina", "incidencias", "mantenimientos", "observaciones", "estado"}


def test_borrador_refleja_las_incidencias_y_el_estado(client, sucursal_id):
    api_incidencias.limitador_qr_token.reiniciar()
    api_incidencias.limitador_qr_ip.reiniciar()
    equipo = _crear_equipo(client, sucursal_id, "EQ-I3")
    token = equipo["qr_activo"]["token"]
    for _ in range(2):
        r = client.post(
            "/api/v1/incidencias/reporte-qr",
            json={"token": token, "tipo_falla_codigo": "ROTA", "gravedad": "grave", "funcional": False, "reportado_por": "Socio"},
        )
        assert r.status_code == 201, r.text
    anio, mes = _mes_actual()
    datos = client.get("/api/v1/informes/borrador", params={"tipo": "mensual", "anio": anio, "mes": mes}).json()
    fila = next(f for f in datos["filas"] if f["codigo"] == "EQ-I3")
    assert fila["incidencias"].startswith("2 incidencias")
    assert fila["estado"] == "Fuera de servicio"


def test_borrador_trimestral_y_anual_dejan_una_fila_por_maquina_y_mes(client, sucursal_id):
    _crear_equipo(client, sucursal_id, "EQ-I4")
    anio, _ = _mes_actual()
    anterior = client.get("/api/v1/informes/borrador", params={"tipo": "anual", "anio": anio - 1}).json()
    # La maquina se registro hoy: todavia no existia en el año anterior si tiene fecha de instalacion;
    # sin fecha se informa los 12 meses. Lo que importa es que nunca se inventen meses futuros.
    assert len(anterior["filas"]) in (0, 12)
    actual = client.get("/api/v1/informes/borrador", params={"tipo": "anual", "anio": anio}).json()
    hoy = periodos.hoy_local()
    assert len(actual["filas"]) == hoy.month  # solo los meses que ya empezaron
    futuro = client.get("/api/v1/informes/borrador", params={"tipo": "anual", "anio": anio + 1}).json()
    assert futuro["filas"] == []


def test_borrador_sin_parametros_toma_el_ultimo_periodo_completo(client, sucursal_id):
    _crear_equipo(client, sucursal_id, "EQ-I5")
    for tipo, meses in (("mensual", 1), ("trimestral", 3), ("anual", 12)):
        r = client.get("/api/v1/informes/borrador", params={"tipo": tipo})
        assert r.status_code == 200 and r.json()["tipo"] == tipo
        assert len(r.json()["filas"]) in (0, meses)


@pytest.mark.parametrize(
    "params",
    [{"tipo": "semanal"}, {"tipo": "mensual", "anio": 2026, "mes": 13}, {"tipo": "trimestral", "anio": 2026, "trimestre": 9},
     {"tipo": "mensual", "anio": 1999, "mes": 1}],
)
def test_borrador_rechaza_parametros_invalidos(client, params):
    assert client.get("/api/v1/informes/borrador", params=params).status_code == 422


def test_excel_con_las_filas_editadas(client):
    openpyxl = pytest.importorskip("openpyxl")
    from io import BytesIO

    cuerpo = {
        "gimnasio": "CAF Duoc UC Puerto Montt",
        "responsable": "Braihan González",
        "etiqueta": "Octubre 2026",
        "desde": "2026-10-01",
        "hasta": "2026-10-31",
        "generado": "2026-11-12",
        "filas": [
            {"fecha": "Octubre 2026", "codigo": "EQ-001", "maquina": "Cinta de correr 1", "incidencias": "Sin incidencias",
             "mantenimientos": "1 inspección (05-10)", "observaciones": "Revisada por el equipo", "estado": "Operativo"},
            {"fecha": "Octubre 2026", "codigo": "EQ-002", "maquina": "=SUMA(1;1)", "incidencias": "1 incidencia", "mantenimientos": "",
             "observaciones": "", "estado": "Fuera de servicio"},
        ],
    }
    r = client.post("/api/v1/informes/excel", json=cuerpo)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert ".xlsx" in r.headers["content-disposition"]
    hoja = openpyxl.load_workbook(BytesIO(r.content)).active
    valores = [[c for c in fila] for fila in hoja.iter_rows(values_only=True)]
    planos = [v for fila in valores for v in fila if v]
    assert "CAF Duoc UC Puerto Montt" in planos and "Braihan González" in planos
    assert "Revisada por el equipo" in planos
    # Una celda que empieza con "=" se guarda como texto, nunca como formula.
    celda = next(c for fila in hoja.iter_rows() for c in fila if c.value == "=SUMA(1;1)")
    assert celda.data_type == "s"


def test_excel_exige_nombre_de_gimnasio(client):
    assert client.post("/api/v1/informes/excel", json={"gimnasio": "", "filas": []}).status_code == 422
