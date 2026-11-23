"""Revisa una corrida del modulo de vision contra las reglas T_on / T_off y el conteo manual.

Uso (desde GymKeep/vision, despues de `procesar ... --verdad conteo_manual.csv`):

    python medicion_vision.py salida/<corrida>

Lee `sesiones.csv` y `resumen.json` de la corrida (no necesita instalar nada) y muestra:
  1. Reglas: cada sesion debe durar al menos T_on, ninguna pausa interna puede llegar a T_off y,
     si una sesion se cerro por ausencia, la siguiente de la misma maquina empieza al menos
     T_off despues.
  2. Error del tiempo de uso frente al conteo manual (solo si la corrida uso --verdad):
     error total = |suma medida - suma real| / suma real, y error estricto = suma de los
     errores absolutos por maquina / suma real. Meta del OE2: error total < 10 %.
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

META_ERROR_PCT = 10.0


def main(carpeta: Path) -> int:
    resumen = json.loads((carpeta / "resumen.json").read_text(encoding="utf-8"))
    with (carpeta / "sesiones.csv").open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    t_on = float(resumen["parametros"]["t_on_s"])
    t_off = float(resumen["parametros"]["t_off_s"])

    print(f"Corrida: {carpeta}  |  video: {resumen['fuente']}  |  T_on {t_on:.0f} s, T_off {t_off:.0f} s")
    por_maquina = defaultdict(list)
    for fila in filas:
        por_maquina[fila["maquina"]].append(fila)

    fallas, total = [], 0
    for maquina, ses in por_maquina.items():
        ses.sort(key=lambda s: float(s["t_inicio_s"]))
        for i, s in enumerate(ses):
            total += 1
            problemas = []
            if float(s["duracion_s"]) < t_on:
                problemas.append(f"dura {s['duracion_s']} s (< T_on)")
            if float(s["pausa_max_s"]) >= t_off:
                problemas.append(f"pausa de {s['pausa_max_s']} s (>= T_off)")
            if i + 1 < len(ses) and s["cierre"] in ("ausencia", "inactividad"):
                hueco = float(ses[i + 1]["t_inicio_s"]) - float(s["t_fin_s"])
                if hueco < t_off:
                    problemas.append(f"la siguiente empieza {hueco:.1f} s despues (< T_off)")
            if problemas:
                fallas.append((maquina, s["t_inicio_s"], "; ".join(problemas)))
    print(f"\nReglas: {total - len(fallas)} de {total} sesiones cumplen las tres comprobaciones")
    for maquina, t, texto in fallas:
        print(f"  NO CUMPLE  {maquina} (t={t} s): {texto}")

    anotadas = [m for m in resumen["maquinas"] if "validacion" in m]
    if not anotadas:
        print("\nSin conteo manual: vuelve a procesar con --verdad conteo_manual.csv para medir el error.")
        return 0 if not fallas else 1

    print(f"\n{'maquina':<24}{'real (s)':>10}{'medido (s)':>12}{'error (s)':>11}{'error %':>9}{'IoU':>7}")
    real = medido = abs_err = 0.0
    for m in anotadas:
        v = m["validacion"]
        r, md = v["uso_real_s"], m["uso_total_s"]
        real, medido, abs_err = real + r, medido + md, abs_err + abs(md - r)
        pct = f"{100 * abs(md - r) / r:.1f}" if r else "-"
        print(f"{m['maquina'][:23]:<24}{r:>10.1f}{md:>12.1f}{md - r:>+11.1f}{pct:>9}{v['iou']:>7.2f}")
    total_pct = 100 * abs(medido - real) / real if real else 0.0
    estricto = 100 * abs_err / real if real else 0.0
    print(f"{'TOTAL':<24}{real:>10.1f}{medido:>12.1f}{medido - real:>+11.1f}{total_pct:>9.1f}")
    print(f"\nError total del tiempo de uso: {total_pct:.1f} %  (meta < {META_ERROR_PCT:.0f} %)  ->  "
          + ("CUMPLE" if total_pct < META_ERROR_PCT else "NO CUMPLE"))
    print(f"Error estricto (suma de errores absolutos por maquina): {estricto:.1f} %")
    return 0 if (not fallas and total_pct < META_ERROR_PCT) else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
