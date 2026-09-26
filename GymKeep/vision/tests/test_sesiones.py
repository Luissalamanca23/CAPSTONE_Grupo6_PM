"""Reglas de interpretacion del uso (§6.6.2): se prueban con presencia sintetica, sin video."""

import pytest

from gymkeep_vision.sesiones import Estado, MonitorMaquina, Observacion, ParametrosUso

P = ParametrosUso(t_on_s=30, t_off_s=90, gracia_s=2, heartbeat_s=60)


def simular(tramos, paso=0.2, parametros=P, t_final=None):
    """tramos: lista de (desde, hasta) en segundos con una persona sobre la maquina."""
    monitor = MonitorMaquina(parametros)
    eventos = []
    fin = t_final if t_final is not None else max(h for _, h in tramos) + parametros.t_off_s + 5
    n = int(round(fin / paso))
    for i in range(n + 1):
        t = i * paso
        presente = any(d <= t <= h for d, h in tramos)
        eventos += monitor.actualizar(Observacion(t=t, personas=int(presente), confianza=0.9 if presente else None))
    eventos += monitor.finalizar(fin)
    return monitor, eventos


def tipos(eventos):
    return [e.tipo for e in eventos]


def test_transeunte_no_abre_sesion():
    monitor, eventos = simular([(10, 25)])  # 15 s < T_on
    assert eventos == []
    assert monitor.sesiones == []
    assert monitor.candidatas_descartadas == 1


def test_uso_continuo_es_una_sesion_con_inicio_retroactivo_y_fin_en_ultima_presencia():
    monitor, eventos = simular([(10, 310)])
    assert tipos(eventos) == ["inicio_uso", "uso_en_curso", "uso_en_curso", "uso_en_curso", "uso_en_curso", "fin_uso"]
    inicio, fin = eventos[0], eventos[-1]
    # El inicio es cuando llego la persona (t=10), aunque se confirma en t=40.
    assert inicio.t == pytest.approx(10)
    assert inicio.t_emision == pytest.approx(40)
    # El fin es la ultima presencia (t=310), no t=310+T_off.
    assert fin.t == pytest.approx(310)
    assert fin.t_emision == pytest.approx(400)
    sesion = monitor.sesiones[0]
    assert sesion.duracion_s == pytest.approx(300)
    assert sesion.presencia_s == pytest.approx(300)
    assert sesion.cierre == "ausencia"


def test_descanso_entre_series_no_parte_la_sesion():
    # 4 series de 45 s con 75 s de descanso (< T_off = 90 s): es UNA sesion, no cuatro.
    series = [(0, 45), (120, 165), (240, 285), (360, 405)]
    monitor, eventos = simular(series)
    assert tipos(eventos).count("inicio_uso") == 1
    assert tipos(eventos).count("fin_uso") == 1
    sesion = monitor.sesiones[0]
    assert sesion.duracion_s == pytest.approx(405)
    assert sesion.presencia_s == pytest.approx(180)
    assert sesion.pausas == 3
    assert sesion.pausa_max_s == pytest.approx(75, abs=0.3)


def test_ausencia_mayor_a_t_off_parte_en_dos_sesiones():
    monitor, eventos = simular([(0, 60), (200, 260)])  # 140 s sin nadie > T_off
    assert tipos(eventos).count("inicio_uso") == 2
    assert [round(s.duracion_s) for s in monitor.sesiones] == [60, 60]


def test_parpadeo_del_detector_no_reinicia_la_candidatura():
    # Huecos de 1 s (< gracia) durante los primeros 30 s: igual se abre la sesion.
    tramos = [(0, 9), (10, 19), (20, 29), (30, 100)]
    monitor, eventos = simular(tramos)
    assert eventos[0].tipo == "inicio_uso"
    assert eventos[0].t == pytest.approx(0)
    assert monitor.candidatas_descartadas == 0


def test_hueco_real_durante_la_candidatura_la_reinicia():
    # 20 s, hueco de 10 s (> gracia), 40 s: la sesion empieza en la segunda aparicion.
    monitor, eventos = simular([(0, 20), (30, 70)])
    assert eventos[0].tipo == "inicio_uso"
    assert eventos[0].t == pytest.approx(30)
    assert monitor.candidatas_descartadas == 1


def test_el_tiempo_de_uso_no_depende_de_los_cuadros_por_segundo():
    # Mismo uso analizado a 10 Hz y a 1 Hz: misma duracion (no se cuentan cuadros).
    lento, _ = simular([(5, 245)], paso=1.0)
    rapido, _ = simular([(5, 245)], paso=0.1)
    assert lento.sesiones[0].duracion_s == pytest.approx(rapido.sesiones[0].duracion_s, abs=1)


def test_fin_de_video_cierra_la_sesion_abierta():
    monitor, eventos = simular([(0, 100)], t_final=100)
    assert eventos[-1].tipo == "fin_uso"
    assert monitor.sesiones[0].cierre == "fin_de_video"
    assert monitor.sesion is None


def test_estado_pausa_visible_mientras_no_se_cumple_t_off():
    monitor = MonitorMaquina(P)
    for i in range(0, 40 * 5 + 1):
        monitor.actualizar(Observacion(t=i * 0.2, personas=1, confianza=0.9))
    assert monitor.estado == Estado.EN_USO
    monitor.actualizar(Observacion(t=50, personas=0))
    assert monitor.estado == Estado.PAUSA
    assert monitor.sesion is not None


def test_dos_personas_en_la_misma_maquina_cuentan_un_solo_uso():
    monitor = MonitorMaquina(P)
    for i in range(0, 100 * 5 + 1):
        monitor.actualizar(Observacion(t=i * 0.2, personas=2, confianza=0.8, track_ids=(1, 2)))
    monitor.finalizar(100)
    sesion = monitor.sesiones[0]
    assert sesion.duracion_s == pytest.approx(100)
    assert sesion.personas_max == 2
    assert sesion.track_ids == {1, 2}


def test_salto_de_tiempo_no_se_imputa_como_presencia():
    # La camara se cae 60 s con la persona encima: la presencia no suma ese hueco (MP-50).
    monitor = MonitorMaquina(P)
    for t in [i * 0.2 for i in range(0, 201)] + [100 + i * 0.2 for i in range(0, 101)]:
        monitor.actualizar(Observacion(t=t, personas=1, confianza=0.9))
    monitor.finalizar(120)
    assert monitor.sesiones[0].presencia_s == pytest.approx(60, abs=0.5)


def test_t_off_debe_superar_la_gracia():
    with pytest.raises(ValueError):
        ParametrosUso(t_off_s=1, gracia_s=2)
