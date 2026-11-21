#!/usr/bin/env python3
"""Compara el uso medido por dos corridas del MISMO video (por ejemplo, perfil normal y --perfil rpi).

    python3 raspberry-pi/comparar_perfiles.py salida_normal/resumen.json salida_rpi/resumen.json

Por cada maquina muestra las sesiones y el tiempo de uso de cada corrida y la diferencia del
perfil rpi frente al normal (en % del uso del normal). Tambien compara los ms por analisis.
Es la medicion de "exactitud frente al perfil normal": no usa conteo manual, solo mide cuanto
cambia el resultado al bajar el costo de calculo.
"""
import json
import sys


def cargar(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    normal, rpi = cargar(sys.argv[1]), cargar(sys.argv[2])
    por_nombre = {m["maquina"]: m for m in rpi["maquinas"]}
    print(f"{'Máquina':<22}{'Normal (s)':>12}{'rpi (s)':>10}{'Dif. (s)':>10}{'Dif. (%)':>10}{'Ses. N/R':>10}")
    total_n = total_r = 0.0
    for m in normal["maquinas"]:
        r = por_nombre.get(m["maquina"])
        if r is None:
            continue
        n_s, r_s = m["uso_total_s"], r["uso_total_s"]
        total_n += n_s
        total_r += r_s
        dif = r_s - n_s
        pct = f"{100 * dif / n_s:+.1f}" if n_s else "—"
        print(f"{m['maquina']:<22}{n_s:>12.1f}{r_s:>10.1f}{dif:>+10.1f}{pct:>10}{m['sesiones']:>5}/{r['sesiones']:<4}")
    if total_n:
        print(f"{'TOTAL':<22}{total_n:>12.1f}{total_r:>10.1f}{total_r - total_n:>+10.1f}{100 * (total_r - total_n) / total_n:>+10.1f}")
    rn, rr = normal.get("rendimiento", {}), rpi.get("rendimiento", {})
    print(f"\nms por análisis: normal {rn.get('ms_por_cuadro')} · rpi {rr.get('ms_por_cuadro')} · "
          f"análisis: normal {rn.get('cuadros_analizados')} · rpi {rr.get('cuadros_analizados')}")
    print(f"Parámetros normal: {normal.get('parametros')}\nParámetros rpi:    {rpi.get('parametros')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
