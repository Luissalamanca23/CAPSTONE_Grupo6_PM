"""Calibracion de parametros sin volver a correr YOLO.

`presencia.csv` guarda, por maquina y por instante analizado, la mayor confianza de las
personas dentro de la ROI. Este modulo vuelve a pasar esa senal por la maquina de estados
con otros parametros (confianza_min, gracia, T_on, T_off) y, si hay verdad de terreno
anotada a mano, mide que tan bien coincide cada combinacion (§8.4.7: MP-45..MP-47 se
calibran con video etiquetado del gimnasio)."""

from __future__ import annotations

import csv
import itertools
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from gymkeep_vision.config import Config
from gymkeep_vision.pipeline import mmss
from gymkeep_vision.sesiones import MonitorMaquina, Observacion

Intervalos = list[tuple[float, float]]


def leer_presencia(ruta: Path) -> dict[str, list[tuple[float, float | None]]]:
    series: dict[str, list[tuple[float, float | None]]] = defaultdict(list)
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            conf = float(fila["confianza_max"]) if fila["confianza_max"] else None
            series[fila["maquina"]].append((float(fila["t_s"]), conf))
    return series


def leer_verdad(ruta: Path) -> dict[str, Intervalos]:
    """Maquina -> intervalos reales. Una maquina que no aparece no fue anotada (no se
    evalua); una fila sin tiempos significa "anotada y sin uso"."""
    verdad: dict[str, Intervalos] = {}
    with ruta.open(encoding="utf-8") as f:
        lineas = [l for l in f if l.strip() and not l.lstrip().startswith("#")]
    for fila in csv.DictReader(lineas):
        intervalos = verdad.setdefault(fila["maquina"], [])
        if fila["inicio_s"]:
            intervalos.append((float(fila["inicio_s"]), float(fila["fin_s"])))
    return verdad


def simular(serie: list[tuple[float, float | None]], cfg: Config, confianza_min: float) -> Intervalos:
    monitor = MonitorMaquina(cfg.uso)
    for t, conf in serie:
        presente = conf is not None and conf >= confianza_min
        monitor.actualizar(Observacion(t=t, personas=int(presente), confianza=conf if presente else None))
    if serie:
        monitor.finalizar(serie[-1][0])
    return [(s.inicio, s.fin) for s in monitor.sesiones]


def medida(intervalos: Intervalos) -> float:
    """Largo de la union de intervalos (lo solapado cuenta una vez)."""
    total, fin_bloque = 0.0, None
    for ini, fin in sorted(intervalos):
        if fin_bloque is None or ini > fin_bloque:
            total += fin - ini
            fin_bloque = fin
        elif fin > fin_bloque:
            total += fin - fin_bloque
            fin_bloque = fin
    return total


def comparar(medidos: Intervalos, reales: Intervalos) -> dict:
    uso_m, uso_r = medida(medidos), medida(reales)
    union = medida(medidos + reales)
    interseccion = uso_m + uso_r - union
    return {
        "uso_medido_s": uso_m,
        "uso_real_s": uso_r,
        "sesiones_medidas": len(medidos),
        "sesiones_reales": len(reales),
        # IoU temporal: 1 = los intervalos medidos calzan exacto con los reales.
        "iou": interseccion / union if union else 1.0,
    }


def barrido(
    series: dict[str, list[tuple[float, float | None]]],
    cfg: Config,
    *,
    confianzas: list[float],
    gracias: list[float],
    t_ons: list[float],
    t_offs: list[float],
    verdad: dict[str, Intervalos] | None,
) -> list[dict]:
    resultados = []
    maquinas = [m.nombre for m in cfg.maquinas]
    for conf, gracia, t_on, t_off in itertools.product(confianzas, gracias, t_ons, t_offs):
        prueba = replace(cfg, uso=replace(cfg.uso, gracia_s=gracia, t_on_s=t_on, t_off_s=t_off))
        fila = {"confianza_min": conf, "gracia_s": gracia, "t_on_s": t_on, "t_off_s": t_off, "maquinas": {}}
        for nombre in maquinas:
            medidos = simular(series.get(nombre, []), prueba, conf)
            anotada = verdad is not None and nombre in verdad
            fila["maquinas"][nombre] = comparar(medidos, verdad[nombre] if anotada else [])
            fila["maquinas"][nombre]["anotada"] = anotada
        if verdad is not None:
            evaluadas = [r for r in fila["maquinas"].values() if r["anotada"]]
            reales = sum(r["uso_real_s"] for r in evaluadas)
            error = sum(abs(r["uso_medido_s"] - r["uso_real_s"]) for r in evaluadas)
            fila["error_uso_pct"] = 100 * error / reales if reales else 0.0
            fila["iou_promedio"] = sum(r["iou"] for r in evaluadas) / len(evaluadas) if evaluadas else 0.0
        resultados.append(fila)
    return resultados


def imprimir(resultados: list[dict], con_verdad: bool) -> str:
    maquinas = list(resultados[0]["maquinas"])
    cabecera = f"{'conf':>5}{'gracia':>7}{'T_on':>6}{'T_off':>6}  " + "".join(f"{m[-14:]:>18}" for m in maquinas)
    if con_verdad:
        cabecera += f"{'error uso':>11}{'IoU prom':>10}"
    lineas = [cabecera]
    if con_verdad:
        real = "".join(
            f"{(mmss(d['uso_real_s']) + ' (real)') if d['anotada'] else 'sin anotar':>18}"
            for d in resultados[0]["maquinas"].values()
        )
        lineas.append(f"{'':>26}{real}")
    for r in resultados:
        celdas = ""
        for m in maquinas:
            d = r["maquinas"][m]
            texto = f"{mmss(d['uso_medido_s'])} {d['sesiones_medidas']}s"
            if con_verdad:
                texto += f" {d['iou']:.2f}" if d["anotada"] else "    -"
            celdas += f"{texto:>18}"
        linea = f"{r['confianza_min']:>5.2f}{r['gracia_s']:>7.0f}{r['t_on_s']:>6.0f}{r['t_off_s']:>6.0f}  {celdas}"
        if con_verdad:
            linea += f"{r['error_uso_pct']:>10.1f}%{r['iou_promedio']:>10.2f}"
        lineas.append(linea)
    lineas.append("")
    lineas.append("Celda por maquina: uso medido, cantidad de sesiones" + (", IoU temporal con la verdad." if con_verdad else "."))
    return "\n".join(lineas)
