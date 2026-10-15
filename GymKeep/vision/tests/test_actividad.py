"""Actividad por pose: usar la maquina frente a solo estar encima (sentado sin entrenar)."""

import math

from gymkeep_vision.actividad import ARTICULACIONES, MedidorActividad, ParametrosActividad
from gymkeep_vision.config import Config, ConfigCamara, ConfigMaquina
from gymkeep_vision.sesiones import Estado, MonitorMaquina, Observacion, ParametrosUso
from gymkeep_vision.zonas import Deteccion

CAJA = (100.0, 100.0, 200.0, 400.0)  # 300 px de alto


def persona(t: float, amplitud: float, track_id: int = 1) -> Deteccion:
    """Persona con las articulaciones oscilando `amplitud` (en alturas de la caja)."""
    desplazamiento = amplitud * 300 * math.sin(2 * math.pi * t / 2)  # una repeticion cada 2 s
    puntos = [(150.0, 200.0, 0.9)] * 17
    puntos = [
        (x, y + desplazamiento, c) if i in ARTICULACIONES else (x, y, c) for i, (x, y, c) in enumerate(puntos)
    ]
    return Deteccion(bbox=CAJA, confianza=0.9, track_id=track_id, puntos=tuple(puntos))


def medir(amplitud: float, segundos: float = 6.0) -> bool | None:
    medidor = MedidorActividad()
    resultado = None
    for k in range(int(segundos / 0.2)):
        det = persona(k * 0.2, amplitud)
        resultado = medidor.actualizar(k * 0.2, [det])[id(det)]
    return resultado


def test_quien_entrena_esta_activo_y_quien_esta_sentado_no():
    assert medir(0.3) is True  # brazos y piernas moviendose (una serie)
    assert medir(0.005) is False  # sentado, solo el temblor del detector


def test_sin_pose_o_sin_track_la_actividad_es_desconocida():
    medidor = MedidorActividad()
    sin_pose = Deteccion(bbox=CAJA, confianza=0.9, track_id=1)
    sin_track = Deteccion(bbox=CAJA, confianza=0.9, puntos=persona(0, 0.1).puntos)
    resultado = medidor.actualizar(0.0, [sin_pose, sin_track])
    assert resultado[id(sin_pose)] is None and resultado[id(sin_track)] is None


def test_recien_aparecida_no_se_decide_hasta_tener_muestras():
    medidor = MedidorActividad(ParametrosActividad(muestras_min=5))
    det = persona(0.0, 0.2)
    assert medidor.actualizar(0.0, [det])[id(det)] is None


def test_la_retencion_cubre_el_punto_muerto_entre_repeticiones():
    medidor = MedidorActividad(ParametrosActividad(ventana_s=2.0, retencion_s=2.0))
    t = 0.0
    for _ in range(20):  # 4 s entrenando
        det = persona(t, 0.3)
        medidor.actualizar(t, [det])
        t += 0.2
    quieto = Deteccion(bbox=CAJA, confianza=0.9, track_id=1, puntos=persona(0, 0).puntos)
    assert medidor.actualizar(t, [quieto])[id(quieto)] is True  # recien se detuvo
    for _ in range(20):  # 4 s quieto: ya salio de la ventana y de la retencion
        t += 0.2
        quieto = Deteccion(bbox=CAJA, confianza=0.9, track_id=1, puntos=persona(0, 0).puntos)
        estado = medidor.actualizar(t, [quieto])[id(quieto)]
    assert estado is False


P = ParametrosUso(t_on_s=30, t_off_s=90, gracia_s=2)


def simular(tramos, paso=0.2):
    """tramos: [(segundos, personas, activas)]."""
    monitor, eventos, t, estados = MonitorMaquina(P), [], 0.0, []
    for duracion, personas, activas in tramos:
        fin = t + duracion
        while t < fin:
            eventos += monitor.actualizar(Observacion(t=t, personas=personas, activas=activas))
            estados.append(monitor.estado)
            t += paso
    return monitor, eventos, estados


def test_sentado_sin_entrenar_no_abre_sesion_y_queda_ocupada():
    monitor, eventos, estados = simular([(120, 1, 0)])
    assert eventos == []
    assert estados[-1] == Estado.OCUPADA


def test_quedarse_quieto_mas_que_t_off_cierra_por_inactividad():
    monitor, eventos, _ = simular([(60, 1, 1), (100, 1, 0)])
    assert [e.tipo for e in eventos] == ["inicio_uso", "fin_uso"]
    assert eventos[-1].sesion.cierre == "inactividad"
    assert monitor.estado == Estado.OCUPADA
    assert abs(eventos[-1].sesion.duracion_s - 60) < 1  # termina en el ultimo movimiento


def test_descanso_quieto_entre_series_no_parte_la_sesion():
    _, eventos, estados = simular([(60, 1, 1), (60, 1, 0), (60, 1, 1)])
    assert [e.tipo for e in eventos].count("inicio_uso") == 1
    assert Estado.PAUSA in estados


def test_sin_medir_actividad_todo_sigue_igual():
    _, eventos, estados = simular([(60, 1, None)])
    assert [e.tipo for e in eventos] == ["inicio_uso"]
    assert Estado.OCUPADA not in estados


def test_con_actividad_se_usa_el_modelo_de_pose():
    cfg = Config(
        camara=ConfigCamara(codigo="CAM"), maquinas=[ConfigMaquina(nombre="M", codigo_activo="EQ", roi=[[0, 0], [1, 0], [1, 1]])]
    ).con_actividad()
    assert cfg.modelo.pesos == "yolo26n-pose.pt" and cfg.actividad is not None
    assert cfg.con_actividad().modelo.pesos == "yolo26n-pose.pt"  # no agrega -pose dos veces
