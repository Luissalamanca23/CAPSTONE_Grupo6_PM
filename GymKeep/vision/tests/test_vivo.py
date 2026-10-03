"""Modo en vivo: configuracion desde la plataforma, envio del estado y zonas en caliente."""

import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from gymkeep_vision import vivo
from gymkeep_vision.config import desde_api
from gymkeep_vision.pipeline import Pipeline, Resultado
from gymkeep_vision.sesiones import Estado, Observacion
from gymkeep_vision.zonas import Deteccion


def configuracion(maquinas=None, **parametros):
    return {
        "camara_id": 3,
        "codigo": "CAM-01",
        "nombre": "Camara cardio",
        "empresa_id": 1,
        "sucursal_id": 1,
        "zona_id": 2,
        "parametros": {"t_on_s": 30, "t_off_s": 90, "confianza_min": 0.5, "gracia_s": 2, "escala_tiempo": 1.0,
                       **parametros},
        "maquinas": maquinas if maquinas is not None else [
            {"equipo_id": 7, "codigo_activo": "EQ-7", "nombre": "Cinta 01", "categoria": "cardio",
             "roi": [[0.1, 0.5], [0.4, 0.5], [0.4, 0.9], [0.1, 0.9]]},
        ],
    }


def test_configuracion_desde_la_plataforma():
    cfg = desde_api(configuracion(confianza_min=0.25, gracia_s=10, escala_tiempo=0.8))
    assert (cfg.camara.id, cfg.camara.codigo, cfg.camara.sucursal_id) == (3, "CAM-01", 1)
    assert cfg.maquinas[0].equipo_id == 7
    assert cfg.resolucion_referencia == (1, 1)  # zonas normalizadas: se escalan al tamano del video
    assert (cfg.confianza_min, cfg.uso.gracia_s, cfg.escala_tiempo) == (0.25, 10, 0.8)


def test_camara_sin_zonas_igual_se_puede_analizar():
    # Sin zonas el pipeline igual envia la imagen, para poder dibujarlas en el panel.
    assert desde_api(configuracion(maquinas=[])).maquinas == []


def esperar(condicion, segundos=3.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return False


def test_publicador_envia_el_ultimo_estado_la_imagen_y_avisa_cambios_de_zonas():
    recibidos = {"vivo": [], "cuadro": []}
    zonas = {"actual": configuracion()}

    def api(peticion: httpx.Request) -> httpx.Response:
        if peticion.url.path.endswith("/vivo"):
            recibidos["vivo"].append(peticion.read())
            return httpx.Response(202, json={"ok": True})
        if peticion.url.path.endswith("/cuadro"):
            recibidos["cuadro"].append(peticion.read())
            return httpx.Response(201, json={})
        return httpx.Response(200, json=zonas["actual"])

    cliente = httpx.Client(base_url="http://api", transport=httpx.MockTransport(api))
    publicador = vivo.PublicadorVivo(
        cliente, 3, cada_estado_s=0.05, cada_cuadro_s=0.05, cada_config_s=0.05,
        huella_config=vivo.huella(zonas["actual"]),
    )
    try:
        # Si llegan varios estados antes del envio, solo viaja el mas reciente.
        publicador.publicar({"n": 1})
        publicador.publicar({"n": 2}, cuadro_jpeg=b"\xff\xd8jpeg")
        assert esperar(lambda: recibidos["vivo"] and recibidos["cuadro"])
        assert b'"n":2' in recibidos["vivo"][0].replace(b" ", b"")
        assert recibidos["cuadro"][0] == b"\xff\xd8jpeg"

        # Sin cambios en la plataforma no hay configuracion nueva...
        time.sleep(0.2)
        assert publicador.tomar_config_nueva() is None
        # ...y cuando alguien edita una zona en el panel, el pipeline se entera.
        zonas["actual"] = configuracion(maquinas=[])
        assert esperar(lambda: publicador._config_nueva is not None)
        assert publicador.tomar_config_nueva()["maquinas"] == []
    finally:
        publicador.cerrar()


def test_api_caida_no_detiene_el_publicador():
    def api_caida(peticion):
        raise httpx.ConnectError("sin red")

    cliente = httpx.Client(base_url="http://api", transport=httpx.MockTransport(api_caida))
    publicador = vivo.PublicadorVivo(cliente, 3, cada_estado_s=0.01, cada_config_s=10)
    try:
        publicador.publicar({"n": 1})
        assert esperar(lambda: publicador._errores >= 1)
        assert publicador._hilo.is_alive()
    finally:
        publicador.cerrar()


@pytest.fixture()
def pipeline(tmp_path: Path):
    cfg = desde_api(configuracion())
    p = Pipeline(cfg, "camara.mp4", tmp_path, destinos=[], inicio_video=datetime(2026, 10, 3, tzinfo=timezone.utc))
    p._ancho, p._alto = 1000, 500
    p._preparar_zonas(1000, 500)
    resultado = Resultado(cfg, "camara.mp4", p.inicio_video, p.monitores)
    return p, resultado


def test_estado_en_vivo_normaliza_las_cajas(pipeline):
    p, _ = pipeline
    persona = Deteccion((200, 150, 300, 400), 0.9, 5)  # pie en (250, 400): dentro de la zona
    estado = p._estado_vivo(12.0, [persona], {"Cinta 01": [persona]}, 0.011, 5.0)
    assert estado["personas"] == [{"caja": [0.2, 0.3, 0.3, 0.8], "confianza": 0.9, "track_id": 5, "equipo_id": 7}]
    assert estado["maquinas"][0]["equipo_id"] == 7
    assert estado["latencia_ms"] == 11.0


def test_zona_editada_no_corta_la_sesion_y_zona_quitada_la_cierra(pipeline):
    p, resultado = pipeline
    monitor = p.monitores["Cinta 01"]
    for i in range(0, 40 * 5 + 1):  # 40 s encima: sesion abierta
        monitor.actualizar(Observacion(t=i * 0.2, personas=1, confianza=0.9))
    assert monitor.estado == Estado.EN_USO

    # Se mueve la zona desde el panel: misma maquina, la sesion sigue.
    movida = configuracion()
    movida["maquinas"][0]["roi"] = [[0.2, 0.5], [0.5, 0.5], [0.5, 0.95], [0.2, 0.95]]
    p._aplicar_config(movida, 40.0, resultado)
    assert p.monitores["Cinta 01"] is monitor and monitor.sesion is not None
    assert p.zonas[0].poligono.tolist()[0] == [200.0, 250.0]  # escalada al tamano del video

    # Se quita la maquina de la camara: su sesion se cierra con fin_uso.
    p._aplicar_config(configuracion(maquinas=[]), 41.0, resultado)
    assert p.monitores == {}
    assert [e["evento"]["tipo"] for e in resultado.eventos] == ["fin_uso"]
    assert resultado.eventos[0]["metadata"]["cierre"] == "zona_quitada"
