#!/usr/bin/env python3
"""Mide GymKeep corriendo en la Raspberry Pi: analisis por segundo, ms por analisis, CPU,
temperatura y limitaciones por calor o voltaje. Solo usa la biblioteca estandar de Python.

Se ejecuta EN la Raspberry, con el sistema levantado y la camara (o el video) procesando:

    python3 raspberry-pi/medir_raspberry.py --duracion 600 --camara CAM-01

Lee la clave del pipeline del .env, consulta cada 5 s el estado en vivo de la API y deja en
raspberry-pi/mediciones/ un CSV con las muestras y un resumen de texto con lo que hay que copiar al
informe. NO inventa nada: si un dato no se puede leer (por ejemplo vcgencmd en otro equipo), lo
anota como "no disponible".

Que significa cada numero (ver LEEME.md, seccion "Que medir"):
- analisis_por_s: cuadros analizados / tiempo desde que arranco el pipeline (lo informa la API).
  Con una camara en vivo es el ritmo real; con un video en --tiempo-real el pipeline lo frena a
  su ritmo configurado, asi que NO mide la capacidad maxima: para eso sirve latencia_ms.
- latencia_ms: lo que tarda el computo de UN analisis (YOLO, seguimiento y reglas).
- capacidad_estimada_por_s = 1000 / latencia media: cuantos analisis por segundo podria sostener
  un nucleo de trabajo seguido. Es una estimacion derivada, no una medicion directa.
"""

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANDERAS = {  # vcgencmd get_throttled (documentacion de Raspberry Pi)
    0: "bajo voltaje ahora",
    1: "frecuencia limitada ahora",
    2: "limitado por temperatura ahora",
    3: "limite suave de temperatura ahora",
    16: "hubo bajo voltaje",
    17: "hubo frecuencia limitada",
    18: "hubo limitacion por temperatura",
    19: "hubo limite suave de temperatura",
}


def ejecutar(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def leer_env() -> dict[str, str]:
    datos: dict[str, str] = {}
    ruta = RAIZ / ".env"
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip()
    return datos


def temperatura_c() -> float | None:
    salida = ejecutar(["vcgencmd", "measure_temp"])  # temp=54.0'C
    if salida and "=" in salida:
        try:
            return float(salida.split("=")[1].split("'")[0])
        except ValueError:
            pass
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


def frecuencia_mhz() -> float | None:
    salida = ejecutar(["vcgencmd", "measure_clock", "arm"])  # frequency(48)=2400000000
    try:
        return int(salida.split("=")[1]) / 1e6 if salida else None
    except (ValueError, IndexError):
        return None


def banderas_throttled() -> int | None:
    salida = ejecutar(["vcgencmd", "get_throttled"])  # throttled=0x0
    try:
        return int(salida.split("=")[1], 16) if salida else None
    except (ValueError, IndexError):
        return None


def cpu_total() -> tuple[int, int]:
    campos = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    return sum(campos), campos[3] + campos[4]  # total, idle + iowait


def cpu_contenedor(nombre: str) -> float | None:
    salida = ejecutar(["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", nombre])
    try:
        return float(salida.rstrip("%")) if salida else None
    except ValueError:
        return None


def api(ruta: str, clave: str, base: str) -> object | None:
    peticion = urllib.request.Request(f"{base}/api/v1{ruta}", headers={"X-Pipeline-Key": clave})
    try:
        with urllib.request.urlopen(peticion, timeout=10) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None


def resumen(valores: list[float]) -> str:
    v = [x for x in valores if x is not None]
    if not v:
        return "no disponible"
    v.sort()
    p95 = v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]
    return f"mínimo {v[0]:.1f} · promedio {statistics.fmean(v):.1f} · p95 {p95:.1f} · máximo {v[-1]:.1f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--duracion", type=int, default=600, help="segundos a medir (por defecto 600)")
    p.add_argument("--camara", default=None, help="codigo de la camara en GymKeep (por defecto VISION_CAMARA del .env)")
    p.add_argument("--api", default="http://127.0.0.1:8000", help="URL de la API vista desde la Pi")
    p.add_argument("--cada", type=int, default=5, help="segundos entre muestras")
    a = p.parse_args()

    env = leer_env()
    clave = env.get("VISION_PIPELINE_KEY")
    if not clave:
        print("Falta VISION_PIPELINE_KEY en el .env (ejecuta desde GymKeep/ en la Raspberry).", file=sys.stderr)
        return 1
    codigo = a.camara or env.get("VISION_CAMARA", "CAM-01")
    camaras = api("/vision/camaras", clave, a.api)
    camara = next((c for c in camaras or [] if c.get("codigo") == codigo), None)
    if camara is None:
        print(f"No se encontro la camara {codigo} en la API ({a.api}). ¿Esta levantado el sistema y la vision?", file=sys.stderr)
        return 1

    modelo = (Path("/proc/device-tree/model").read_text().strip("\0\n") if Path("/proc/device-tree/model").exists() else "no disponible")
    memoria_kb = next((int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal")), 0)
    fuente = env.get("VISION_FUENTE", "no disponible")
    if "@" in fuente:  # no dejar usuario ni clave de la camara en el informe
        fuente = fuente.split("://")[0] + "://***@" + fuente.split("@", 1)[1]
    opciones = env.get("VISION_OPCIONES", "--perfil rpi")

    destino = Path(__file__).resolve().parent / "mediciones"
    destino.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_csv = destino / f"medicion_{marca}.csv"
    columnas = ["t_s", "temp_c", "freq_mhz", "throttled_hex", "cpu_total_pct", "cpu_vision_pct", "analisis_por_s", "latencia_ms", "en_linea"]
    muestras: list[dict] = []
    t0 = time.monotonic()
    total0, idle0 = cpu_total()
    print(f"Midiendo {a.duracion} s en {modelo} (camara {codigo}). Ctrl+C para cortar y guardar lo medido.")
    try:
        with ruta_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columnas)
            w.writeheader()
            while time.monotonic() - t0 < a.duracion:
                time.sleep(a.cada)
                total1, idle1 = cpu_total()
                cpu = 100 * (1 - (idle1 - idle0) / max(1, total1 - total0))
                total0, idle0 = total1, idle1
                vivo = api(f"/vision/camaras/{camara['id']}/vivo", clave, a.api) or {}
                banderas = banderas_throttled()
                fila = {
                    "t_s": round(time.monotonic() - t0),
                    "temp_c": temperatura_c(),
                    "freq_mhz": frecuencia_mhz(),
                    "throttled_hex": hex(banderas) if banderas is not None else "",
                    "cpu_total_pct": round(cpu, 1),
                    "cpu_vision_pct": cpu_contenedor("gymkeep_vision"),
                    "analisis_por_s": vivo.get("fps_analisis"),
                    "latencia_ms": vivo.get("latencia_ms"),
                    "en_linea": vivo.get("en_linea"),
                }
                w.writerow(fila)
                f.flush()
                muestras.append(fila)
    except KeyboardInterrupt:
        print("Interrumpido: se resume lo medido hasta ahora.")

    def col(nombre: str) -> list[float]:
        return [m[nombre] for m in muestras if isinstance(m[nombre], (int, float))]

    lat = col("latencia_ms")
    aps = col("analisis_por_s")
    ultimo_thr = next((int(m["throttled_hex"], 16) for m in reversed(muestras) if m["throttled_hex"]), None)
    hubo = [BANDERAS[b] for b in BANDERAS if ultimo_thr is not None and ultimo_thr & (1 << b)]
    lineas = [
        f"Medición del {datetime.now():%Y-%m-%d %H:%M} · {len(muestras)} muestras cada {a.cada} s ({a.duracion} s pedidos)",
        f"Equipo: {modelo} · RAM {memoria_kb / 1048576:.1f} GB",
        f"Opciones de visión: {opciones}",
        f"Fuente: {fuente}",
        f"Cámaras analizando en este equipo durante la medición: 1 ({codigo})",
        "",
        f"Análisis por segundo (API, promedio desde el arranque): {resumen(aps)}",
        f"Latencia por análisis, ms (API): {resumen(lat)}",
        (f"Capacidad estimada por cámara: {1000 / statistics.fmean(lat):.1f} análisis/s (derivada de la latencia media; no medida directamente)" if lat else "Capacidad estimada: no disponible"),
        f"CPU total del equipo, % (100 % = los 4 núcleos): {resumen(col('cpu_total_pct'))}",
        f"CPU del contenedor de visión, % (100 % = un núcleo): {resumen(col('cpu_vision_pct'))}",
        f"Temperatura, °C: {resumen(col('temp_c'))}",
        f"Frecuencia del procesador, MHz: {resumen(col('freq_mhz'))}",
        "Limitaciones por calor o voltaje (vcgencmd get_throttled): " + (", ".join(hubo) if hubo else ("ninguna" if ultimo_thr is not None else "no disponible")),
        f"CSV con las muestras: {ruta_csv.relative_to(RAIZ)}",
    ]
    ruta_txt = destino / f"medicion_{marca}.txt"
    ruta_txt.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print(f"\nResumen guardado en {ruta_txt.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
