import pytest

from gymkeep_vision.config import Config, ConfigCamara, ConfigMaquina
from gymkeep_vision.recalibrar import barrido, comparar, medida, simular
from gymkeep_vision.sesiones import ParametrosUso

CFG = Config(
    camara=ConfigCamara(codigo="CAM"),
    maquinas=[ConfigMaquina(nombre="Cinta", codigo_activo="EQ", roi=[[0, 0], [1, 0], [1, 1]])],
    uso=ParametrosUso(t_on_s=30, t_off_s=90, gracia_s=2),
)


def serie(tramos, conf=0.4, fin=600, paso=0.2):
    return [
        (i * paso, conf if any(a <= i * paso <= b for a, b in tramos) else None)
        for i in range(int(fin / paso) + 1)
    ]


def test_medida_cuenta_la_union():
    assert medida([(0, 10), (5, 20), (30, 40)]) == pytest.approx(30)
    assert medida([]) == 0


def test_comparar_iou():
    r = comparar([(0, 100)], [(50, 150)])
    assert r["iou"] == pytest.approx(50 / 150)
    assert comparar([], [])["iou"] == 1.0


def test_simular_respeta_el_umbral_de_confianza():
    datos = serie([(10, 300)], conf=0.4)
    assert simular(datos, CFG, 0.5) == []
    assert simular(datos, CFG, 0.3) == [(pytest.approx(10), pytest.approx(300))]


def test_barrido_con_verdad():
    datos = {"Cinta": serie([(10, 300)], conf=0.4)}
    filas = barrido(datos, CFG, confianzas=[0.3, 0.5], gracias=[2], t_ons=[30], t_offs=[90], verdad={"Cinta": [(10, 300)]})
    assert [round(f["iou_promedio"], 2) for f in filas] == [1.0, 0.0]
    assert filas[1]["error_uso_pct"] == pytest.approx(100)


def test_maquina_sin_anotar_no_entra_en_el_error(tmp_path):
    from gymkeep_vision.recalibrar import leer_verdad

    ruta = tmp_path / "verdad.csv"
    ruta.write_text("# comentario\nmaquina,inicio_s,fin_s,nota\nCinta,10,300,\nBici,,,sin uso\n", encoding="utf-8")
    verdad = leer_verdad(ruta)
    assert verdad == {"Cinta": [(10.0, 300.0)], "Bici": []}

    cfg = Config(
        camara=ConfigCamara(codigo="CAM"),
        maquinas=[
            ConfigMaquina(nombre=n, codigo_activo=n, roi=[[0, 0], [1, 0], [1, 1]]) for n in ("Cinta", "Bici", "Remo")
        ],
        uso=CFG.uso,
    )
    datos = {"Cinta": serie([(10, 300)]), "Bici": serie([]), "Remo": serie([(0, 500)])}
    fila = barrido(datos, cfg, confianzas=[0.3], gracias=[2], t_ons=[30], t_offs=[90], verdad=verdad)[0]
    assert fila["maquinas"]["Remo"]["anotada"] is False
    assert fila["error_uso_pct"] == pytest.approx(0)  # Remo mide uso, pero no se evalua
    assert fila["iou_promedio"] == pytest.approx(1.0)
