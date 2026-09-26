"""Resultados de una corrida: sesiones.csv, resumen.json y linea_de_tiempo.png.

El grafico muestra en una misma fila por maquina las detecciones crudas (marcas grises)
y las sesiones que quedaron despues de aplicar T_on / T_off (barras azules): es la forma
mas directa de explicar que "deteccion != uso"."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from gymkeep_vision.pipeline import Resultado, mmss

AZUL = "#2a78d6"
GRIS_DETECCION = "#b9b8b0"
VERDAD = "#52514e"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
SUPERFICIE = "#fcfcfb"
REJILLA = "#e6e5e0"


def generar(resultado: Resultado, salida: Path, verdad: dict[str, list[tuple[float, float]]] | None = None) -> dict:
    """`verdad` (opcional): intervalos de uso anotados a mano por maquina, en segundos reales
    desde el inicio del video. Si se entrega, el resumen incluye error e IoU por maquina y
    el grafico agrega una fila con el uso real."""
    cfg = resultado.config
    periodo_s = max(0.0, resultado.t_final_s - resultado.t_inicio_s)
    inicio = resultado.inicio_video

    filas = []
    for maquina in cfg.maquinas:
        for s in resultado.monitores[maquina.nombre].sesiones:
            filas.append(
                {
                    "maquina": maquina.nombre,
                    "codigo_activo": maquina.codigo_activo,
                    "equipo_id": maquina.equipo_id,
                    "inicio": (inicio + timedelta(seconds=s.inicio)).isoformat(timespec="seconds"),
                    "fin": (inicio + timedelta(seconds=s.fin)).isoformat(timespec="seconds"),
                    "t_inicio_s": round(s.inicio, 1),
                    "t_fin_s": round(s.fin, 1),
                    "duracion_s": round(s.duracion_s, 1),
                    "presencia_s": round(s.presencia_s, 1),
                    "pausas": s.pausas,
                    "pausa_max_s": round(s.pausa_max_s, 1),
                    "personas_max": s.personas_max,
                    "confianza_promedio": round(s.confianza_promedio or 0, 3),
                    "cierre": s.cierre,
                }
            )
    with (salida / "sesiones.csv").open("w", newline="", encoding="utf-8") as f:
        campos = list(filas[0]) if filas else ["maquina"]
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas)

    maquinas = []
    for maquina in cfg.maquinas:
        monitor = resultado.monitores[maquina.nombre]
        duraciones = [s.duracion_s for s in monitor.sesiones]
        uso = sum(duraciones)
        maquinas.append(
            {
                "maquina": maquina.nombre,
                "codigo_activo": maquina.codigo_activo,
                "equipo_id": maquina.equipo_id,
                "sesiones": len(duraciones),
                "uso_total_s": round(uso, 1),
                "uso_total": mmss(uso),
                "ocupacion_pct": round(100 * uso / periodo_s, 1) if periodo_s else 0.0,
                "sesion_promedio_s": round(uso / len(duraciones), 1) if duraciones else 0.0,
                "sesion_mas_larga_s": round(max(duraciones), 1) if duraciones else 0.0,
                "presencias_descartadas": monitor.candidatas_descartadas,
            }
        )
        if verdad is not None and maquina.nombre in verdad:
            from gymkeep_vision.recalibrar import comparar

            cmp = comparar([(s.inicio, s.fin) for s in monitor.sesiones], verdad[maquina.nombre])
            maquinas[-1]["validacion"] = {
                "uso_real_s": round(cmp["uso_real_s"], 1),
                "error_s": round(uso - cmp["uso_real_s"], 1),
                "iou": round(cmp["iou"], 3),
            }

    resumen = {
        "fuente": Path(resultado.fuente).name,
        "camara": cfg.camara.codigo,
        "inicio_observado": (inicio + timedelta(seconds=resultado.t_inicio_s)).isoformat(timespec="seconds"),
        "fin_observado": (inicio + timedelta(seconds=resultado.t_final_s)).isoformat(timespec="seconds"),
        "periodo_observado_s": round(periodo_s, 1),
        "interrumpido": resultado.interrumpido,
        "modelo": {
            "pesos": Path(cfg.modelo.pesos).name,
            "tracker": cfg.modelo.tracker,
            "imgsz": cfg.modelo.imgsz,
        },
        "parametros": {
            "t_on_s": cfg.uso.t_on_s,
            "t_off_s": cfg.uso.t_off_s,
            "confianza_min": cfg.confianza_min,
            "gracia_s": cfg.uso.gracia_s,
            "intervalo_analisis_s": cfg.intervalo_analisis_s,
            "criterio_zona": cfg.criterio_zona,
        },
        "rendimiento": {
            "cuadros_analizados": resultado.cuadros_analizados,
            "ms_por_cuadro": round(1000 * resultado.segundos_computo / max(1, resultado.cuadros_analizados), 1),
        },
        "eventos": {
            tipo: sum(1 for e in resultado.eventos if e["evento"]["tipo"] == tipo)
            for tipo in ("inicio_uso", "uso_en_curso", "fin_uso")
        },
        "maquinas": maquinas,
    }
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")

    presencia = _leer_presencia(salida / "presencia.csv")
    _grafico(resultado, presencia, salida / "linea_de_tiempo.png", verdad)
    return resumen


def _leer_presencia(ruta: Path) -> dict[str, list[float]]:
    instantes: dict[str, list[float]] = defaultdict(list)
    if not ruta.exists():
        return instantes
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if int(fila["personas"]) > 0:
                instantes[fila["maquina"]].append(float(fila["t_s"]))
    return instantes


def _grafico(resultado: Resultado, presencia: dict[str, list[float]], ruta: Path, verdad=None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter, MultipleLocator

    cfg = resultado.config
    nombres = [m.nombre for m in cfg.maquinas]
    t0, t1 = resultado.t_inicio_s, max(resultado.t_final_s, resultado.t_inicio_s + 1)

    alto_fila = 0.8 if verdad is not None else 0.62
    fig, ax = plt.subplots(figsize=(12, 1.1 + alto_fila * len(nombres)), dpi=150)
    fig.patch.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)

    for fila, nombre in enumerate(nombres):
        y = len(nombres) - 1 - fila
        # Carril superior delgado: cada analisis con alguien dentro de la ROI.
        ts = presencia.get(nombre, [])
        if ts:
            ax.vlines(ts, y + 0.24, y + 0.40, color=GRIS_DETECCION, linewidth=0.6)
        # Carril principal: las sesiones consolidadas.
        sesiones = resultado.monitores[nombre].sesiones
        barra = (y - 0.16, 0.34) if verdad is not None else (y - 0.30, 0.46)
        ax.broken_barh(
            [(s.inicio, max(s.duracion_s, 0.5)) for s in sesiones],
            barra,
            facecolors=AZUL,
            edgecolor=SUPERFICIE,
            linewidth=1.5,
        )
        for s in sesiones:
            # Etiqueta solo si cabe dentro de la barra: nunca un numero encima de otro.
            if s.duracion_s / (t1 - t0) > 0.06:
                ax.text(
                    s.inicio + s.duracion_s / 2, barra[0] + barra[1] / 2, mmss(s.duracion_s),
                    ha="center", va="center", fontsize=7.5, color="white",
                )

        if verdad is not None:
            # Carril inferior: el uso real anotado a mano, para comparar a simple vista.
            ax.broken_barh(
                [(a, b - a) for a, b in verdad.get(nombre, [])], (y - 0.40, 0.13),
                facecolors=VERDAD, edgecolor=SUPERFICIE, linewidth=1.0,
            )

    ax.set_yticks(range(len(nombres)))
    ax.set_yticklabels(list(reversed(nombres)), fontsize=9, color=TEXTO)
    ax.set_xlim(t0, t1)
    ax.set_ylim(-0.6, len(nombres) - 0.4)
    paso = next((p for p in (10, 30, 60, 120, 300, 600, 900, 1800, 3600) if (t1 - t0) / p <= 10), 7200)
    ax.xaxis.set_major_locator(MultipleLocator(paso))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: mmss(v)))
    ax.tick_params(axis="x", colors=TEXTO_SECUNDARIO, labelsize=8)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.set_xlabel("tiempo desde el inicio del video (mm:ss, reloj real)", fontsize=8.5, color=TEXTO_SECUNDARIO)

    uso = cfg.uso
    ax.set_title(
        f"Uso por maquina: {Path(resultado.fuente).name}\n"
        f"T_on {uso.t_on_s:.0f} s · T_off {uso.t_off_s:.0f} s · confianza ≥ {cfg.confianza_min:.2f}",
        loc="left", fontsize=10, color=TEXTO,
    )
    leyenda = [
        Line2D([0], [0], color=GRIS_DETECCION, linewidth=1.5, label="persona detectada en la ROI"),
        Patch(facecolor=AZUL, label="sesion de uso (tras T_on / T_off)"),
    ]
    if verdad is not None:
        leyenda.append(Patch(facecolor=VERDAD, label="uso real (anotado a mano)"))
    ax.legend(
        handles=leyenda,
        loc="upper right", bbox_to_anchor=(1, 1.16), ncol=len(leyenda), frameon=False, fontsize=8,
        labelcolor=TEXTO_SECUNDARIO,
    )
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def imprimir(resumen: dict) -> str:
    lineas = [
        f"Periodo observado: {resumen['inicio_observado']} -> {resumen['fin_observado']}"
        f" ({mmss(resumen['periodo_observado_s'])})",
        "",
        f"{'Maquina':<24}{'Sesiones':>9}{'Uso total':>11}{'Ocupacion':>11}{'Promedio':>10}{'Descart.':>10}"
        + (f"{'Uso real':>12}{'IoU':>7}" if any("validacion" in m for m in resumen["maquinas"]) else ""),
    ]
    for m in resumen["maquinas"]:
        linea = (
            f"{m['maquina']:<24}{m['sesiones']:>9}{m['uso_total']:>11}{m['ocupacion_pct']:>10.1f}%"
            f"{mmss(m['sesion_promedio_s']):>10}{m['presencias_descartadas']:>10}"
        )
        if "validacion" in m:
            linea += f"{mmss(m['validacion']['uso_real_s']):>12}{m['validacion']['iou']:>7.2f}"
        elif any("validacion" in otra for otra in resumen["maquinas"]):
            linea += f"{'sin anotar':>12}{'-':>7}"
        lineas.append(linea)
    return "\n".join(lineas)
