"""Registro y visualizacion del tiempo: hora de inicio, reloj del video anotado y cronometros."""

import shutil
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from gymkeep_vision import tiempo
from gymkeep_vision.sesiones import Estado, MonitorMaquina, Observacion, ParametrosUso

SANTIAGO = ZoneInfo("America/Santiago")


def test_periodo_de_salida_respeta_la_escala_de_tiempo():
    # Archivo normal: 1 de cada 6 cuadros a 30 fps = 0,2 s reales por cuadro anotado.
    assert tiempo.periodo_salida(30, 6, 1.0) == pytest.approx(0.2)
    # Grabador que exporto acelerado: cada cuadro del archivo dura menos tiempo real.
    assert tiempo.periodo_salida(25, 6, 0.843) == pytest.approx(0.20232)


def test_cuadros_pendientes_mantiene_el_video_al_ritmo_del_reloj():
    # Analisis a tiempo: un cuadro escrito por cada periodo.
    assert tiempo.cuadros_pendientes(0.0, 0.0, 0.2, 0) == 1
    assert tiempo.cuadros_pendientes(0.2, 0.0, 0.2, 1) == 1
    # En vivo el analisis se atraso 0,6 s: se repite el cuadro para no adelantar el video.
    assert tiempo.cuadros_pendientes(0.8, 0.0, 0.2, 2) == 3
    # Nunca negativo (si llegan dos cuadros en el mismo periodo, el segundo no se escribe).
    assert tiempo.cuadros_pendientes(0.25, 0.0, 0.2, 2) == 0


def test_inicio_por_argumento_tiene_prioridad_y_toma_la_zona_horaria():
    inicio, origen = tiempo.resolver_inicio("no_existe.mp4", "2026-09-26T18:00:00", SANTIAGO)
    assert origen == tiempo.ORIGEN_ARGUMENTO
    assert inicio.tzinfo is not None
    assert inicio.hour == 18


def test_inicio_desde_metadatos_se_pasa_a_la_hora_local(monkeypatch):
    monkeypatch.setattr(
        tiempo, "leer_creation_time", lambda ruta: datetime(2026, 9, 26, 21, 0, tzinfo=timezone.utc)
    )
    inicio, origen = tiempo.resolver_inicio("video.mp4", None, SANTIAGO)
    assert origen == tiempo.ORIGEN_METADATOS
    assert inicio.hour == 18  # 21:00 UTC = 18:00 en Chile (septiembre, UTC-3)


def test_sin_argumento_ni_metadatos_usa_la_hora_de_procesamiento():
    ahora = datetime(2026, 10, 3, 12, 0, tzinfo=SANTIAGO)
    inicio, origen = tiempo.resolver_inicio("rtsp://camara/stream", None, SANTIAGO, ahora=ahora)
    assert (inicio, origen) == (ahora, tiempo.ORIGEN_AHORA)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requiere ffmpeg")
def test_lee_creation_time_de_un_video_real(tmp_path):
    def crear(nombre, creation_time):
        ruta = tmp_path / nombre
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.2",
             "-metadata", f"creation_time={creation_time}", str(ruta)],
            check=True,
        )
        return ruta

    assert tiempo.leer_creation_time(crear("ok.mp4", "2024-05-01T10:00:00Z")) == datetime(
        2024, 5, 1, 10, 0, tzinfo=timezone.utc
    )
    # 1970 = metadato vacio de algunos codificadores: no es una hora real.
    assert tiempo.leer_creation_time(crear("cero.mp4", "1970-01-01T00:00:00Z")) is None


def test_formatos_para_mostrar_y_para_registrar():
    inicio = datetime(2026, 9, 26, 18, 0, tzinfo=SANTIAGO)
    assert tiempo.hora(inicio) == "26/09/2026 18:00:00"
    assert tiempo.marca(inicio, 1.2345) == "2026-09-26T18:00:01.234-03:00"


P = ParametrosUso(t_on_s=30, t_off_s=90, gracia_s=2, heartbeat_s=60)


def test_progreso_muestra_cuanto_falta_para_t_on_y_t_off():
    monitor = MonitorMaquina(P)
    for i in range(0, 12 * 5 + 1):  # 12 s con alguien encima: todavia detectando
        monitor.actualizar(Observacion(t=i * 0.2, personas=1, confianza=0.9))
    assert monitor.estado == Estado.CANDIDATA
    assert monitor.progreso(12.0) == (pytest.approx(12.0), 30)

    for i in range(61, 40 * 5 + 1):  # sigue hasta los 40 s: sesion abierta
        monitor.actualizar(Observacion(t=i * 0.2, personas=1, confianza=0.9))
    assert monitor.progreso(40.0) is None  # en uso no corre ninguna cuenta regresiva

    monitor.actualizar(Observacion(t=55.0, personas=0))  # se baja hace 15 s
    assert monitor.estado == Estado.PAUSA
    assert monitor.progreso(55.0) == (pytest.approx(15.0), 90)


def test_sesiones_total_cuenta_la_sesion_en_curso():
    monitor = MonitorMaquina(P)
    for i in range(0, 40 * 5 + 1):
        monitor.actualizar(Observacion(t=i * 0.2, personas=1, confianza=0.9))
    assert len(monitor.sesiones) == 0
    assert monitor.sesiones_total == 1
    monitor.finalizar(40.0)
    assert monitor.sesiones_total == 1
