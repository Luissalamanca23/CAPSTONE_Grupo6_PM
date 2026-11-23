"""Medicion completa de la API de GymKeep (RNF-02: p95 < 500 ms), de una sola vez.

Hace todo lo de la guia de prueba de carga: anota el equipo y la version, cuenta los registros de la
base, corre prueba_carga.py 3 veces (1 y 10 usuarios simultaneos), y deja en una carpeta los CSV y un
informe_prueba_carga.md con las tablas llenas, la conclusion y el texto para el informe.

Uso (PowerShell, desde la carpeta GymKeep, con el sistema levantado):

    .\\.venv\\Scripts\\python.exe medir_api.py --run 12345678-9 --token TOKEN_DEL_QR

La clave se pide por teclado (no queda en el historial) o se toma de la variable GYMKEEP_CLAVE.
prueba_carga.py debe estar en la misma carpeta que este archivo. Solo usa la biblioteca estandar.
"""
import argparse
import csv
import getpass
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

UMBRAL = 500.0
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
SQL = ("SELECT (SELECT COUNT(*) FROM equipos), (SELECT COUNT(*) FROM incidencias), "
       "(SELECT COUNT(*) FROM mantenimientos), (SELECT COUNT(*) FROM sesiones_uso);")


def ejecutar(cmd, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 60), **kw)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def memoria_gb():
    try:
        if os.name == "nt":
            import ctypes

            class MEM(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("u", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("a", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = MEM(); m.l = ctypes.sizeof(MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.total / 2**30)
        with open("/proc/meminfo") as f:
            return round(int(f.readline().split()[1]) / 2**20)
    except Exception:
        return None


def procesador():
    if os.name == "nt":
        out = ejecutar(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"])
        if out:
            return out
    return platform.processor() or platform.machine()


def registros_base():
    out = ejecutar(["docker", "compose", "exec", "-T", "db", "psql", "-U", "gymkeep", "-d", "gymkeep", "-t", "-A", "-F", ",", "-c", SQL])
    m = re.search(r"(\d+),(\d+),(\d+),(\d+)", out)
    return [int(x) for x in m.groups()] if m else None


def leer(csv_path):
    with open(csv_path, encoding="utf-8") as f:
        return [{**r, "concurrencia": int(r["concurrencia"]), "errores": int(r["errores"]),
                 **{k: float(r[k]) for k in ("min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")}} for r in csv.DictReader(f)]


def fecha_larga(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="RUN del usuario del panel")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--token", help="token de un QR activo (para medir tambien el portal publico)")
    ap.add_argument("--corridas", type=int, default=3)
    ap.add_argument("--peticiones", type=int, default=100)
    ap.add_argument("--espera", type=int, default=60, help="segundos de pausa entre corridas (60)")
    ap.add_argument("--responsable", default="", help="quien hace la medicion")
    a = ap.parse_args()

    aqui = Path(__file__).resolve().parent
    script = aqui / "prueba_carga.py"
    if not script.exists():
        sys.exit(f"No encuentro {script}. Dejalo en la misma carpeta que medir_api.py.")
    clave = os.environ.get("GYMKEEP_CLAVE") or getpass.getpass("Clave del usuario del panel: ")
    env = {**os.environ, "GYMKEEP_CLAVE": clave}

    ahora = datetime.now()
    carpeta = Path(f"resultados_carga_{ahora:%Y%m%d_%H%M}")
    carpeta.mkdir(exist_ok=True)

    commit = ejecutar(["git", "rev-parse", "--short", "HEAD"]) or "(no disponible)"
    cpu, ram = procesador(), memoria_gb()
    sistema = f"{platform.system()} {platform.release()}"
    regs = registros_base()
    print(f"Equipo: {cpu} · {ram} GB · {sistema} · commit {commit}")
    print("Registros en la base: " + (f"equipos {regs[0]}, incidencias {regs[1]}, mantenimientos {regs[2]}, sesiones {regs[3]}" if regs
          else "no se pudieron contar (docker no respondio): anotalos a mano en el informe"))

    archivos = []
    veredictos = []
    for i in range(1, a.corridas + 1):
        print(f"\n=== Corrida {i} de {a.corridas} ===")
        salida = carpeta / f"corrida{i}.csv"
        cmd = [sys.executable, str(script), "--url", a.url, "--run", a.run, "--peticiones", str(a.peticiones),
               "--concurrencia", "1", "10", "--salida", str(salida)]
        if a.token:
            cmd += ["--token", a.token]
        r = subprocess.run(cmd, env=env)
        if not salida.exists():
            sys.exit("La corrida no produjo resultados (revisa la direccion, el RUN y la clave).")
        archivos.append(salida)
        veredictos.append(r.returncode == 0)
        if i < a.corridas:
            print(f"Pausa de {a.espera} s antes de la siguiente corrida...")
            time.sleep(a.espera)

    corridas = [leer(p) for p in archivos]
    rutas = []
    for f in corridas[0]:
        if f["ruta"] not in rutas:
            rutas.append(f["ruta"])
    sel = lambda c, conc, ruta: next((x for x in c if x["concurrencia"] == conc and x["ruta"] == ruta), None)

    # --- resumen con 1 usuario ---
    resumen, fuera = [], []
    p95_max, ruta_max = 0.0, ""
    for ruta in rutas:
        fs = [sel(c, 1, ruta) for c in corridas]
        if any(x is None for x in fs):
            continue
        errores = sum(x["errores"] for x in fs)
        ok = all(x["p95_ms"] < UMBRAL for x in fs) and errores == 0
        resumen.append((ruta, [x["p95_ms"] for x in fs], errores, ok))
        mayor = max(x["p95_ms"] for x in fs)
        if mayor > p95_max:
            p95_max, ruta_max = mayor, ruta
        if not ok:
            fuera.append((ruta, mayor, errores))
    cumple = bool(resumen) and not fuera

    # --- 10 usuarios ---
    hall, p95_10 = [], 0.0
    for ruta in rutas:
        fs = [sel(c, 10, ruta) for c in corridas]
        fs = [x for x in fs if x]
        if fs:
            m = max(x["p95_ms"] for x in fs)
            p95_10 = max(p95_10, m)
            e = sum(x["errores"] for x in fs)
            if m >= UMBRAL or e:
                hall.append((ruta, m, e))

    L = []
    L.append("# Prueba de carga de la API de GymKeep (RNF-02: p95 < 500 ms)\n")
    L.append("## 1. Datos de la prueba\n")
    L.append("| Dato | Valor |\n|---|---|")
    L.append(f"| Fecha y responsable | {fecha_larga(ahora)}, {ahora:%H:%M} · {a.responsable or '(completar)'} |")
    L.append(f"| Versión del sistema (commit) | {commit} |")
    L.append(f"| Equipo (procesador, memoria, sistema) | {cpu} · {ram if ram else '__'} GB · {sistema} |")
    if regs:
        L.append(f"| Registros en la base | equipos: {regs[0]} · incidencias: {regs[1]} · mantenimientos: {regs[2]} · sesiones: {regs[3]} |")
    else:
        L.append("| Registros en la base | equipos: __ · incidencias: __ · mantenimientos: __ · sesiones: __ (completar) |")
    L.append(f"| Peticiones por ruta y usuarios simultáneos | {a.peticiones} peticiones · usuarios: 1 y 10 · {a.corridas} corridas |")
    L.append(f"| Archivos CSV guardados | {', '.join(p.name for p in archivos)} (carpeta {carpeta.name}) |\n")

    L.append("## 2. Resultado de cada corrida\n")
    for i, c in enumerate(corridas, 1):
        for conc in (1, 10):
            fs = [x for x in c if x["concurrencia"] == conc]
            if not fs:
                continue
            L.append(f"**Corrida {i} · {conc} usuario(s) simultáneo(s)**\n")
            L.append("| Ruta | Err. | Mín | p50 | p95 | p99 | Máx | p95 < 500 ms |\n|---|---|---|---|---|---|---|---|")
            for x in fs:
                L.append(f"| {x['ruta']} | {x['errores']} | {x['min_ms']:g} | {x['p50_ms']:g} | {x['p95_ms']:g} | {x['p99_ms']:g} | {x['max_ms']:g} | {'Sí' if x['cumple'] == 'SI' else 'No'} |")
            L.append("")

    L.append("## 3. Resumen de las corridas (1 usuario, p95 en ms)\n")
    L.append("| Ruta | " + " | ".join(f"Corrida {i}" for i in range(1, a.corridas + 1)) + " | Errores | ¿Cumple? |")
    L.append("|---|" + "---|" * a.corridas + "---|---|")
    for ruta, p95s, e, ok in resumen:
        L.append(f"| {ruta} | " + " | ".join(f"{v:g}" for v in p95s) + f" | {e} | {'Sí' if ok else 'No'} |")
    L.append("")

    L.append("## 4. Conclusión\n")
    L.append(f"- **Resultado:** {'Cumple (todas las rutas con p95 < 500 ms y 0 errores en las ' + str(a.corridas) + ' corridas)' if cumple else 'No cumple'}.")
    if fuera:
        L.append("- **Rutas fuera de la meta:** " + "; ".join(f"{r} (p95 {m:g} ms, {e} errores)" for r, m, e in fuera) + ".")
    else:
        L.append("- **Rutas fuera de la meta:** ninguna.")
    if hall:
        L.append("- **Con 10 usuarios simultáneos (hallazgos):** " + "; ".join(f"{r} (p95 {m:g} ms, {e} errores)" for r, m, e in hall) + ".")
    else:
        L.append(f"- **Con 10 usuarios simultáneos:** ninguna ruta pasó de 500 ms (p95 más alto: {p95_10:g} ms).")
    L.append("- **Acción y fecha de la nueva medición:** " + ("no corresponde." if cumple else "(completar: qué se cambia y cuándo se vuelve a medir)."))
    L.append("")

    n = lambda i: regs[i] if regs else "__"
    L.append("## 5. Texto para el informe (resultado del OE5)\n")
    texto = (f"El {fecha_larga(ahora)} se midió el tiempo de respuesta de {len(rutas)} rutas de la API con la base de demostración "
             f"({n(0)} equipos, {n(1)} incidencias, {n(2)} mantenciones y {n(3)} sesiones de uso), con {a.peticiones} peticiones por ruta, "
             f"1 usuario y {a.corridas} corridas, en un equipo con {cpu} y {ram if ram else '__'} GB de memoria. ")
    if cumple:
        texto += f"El p95 más alto fue de {p95_max:g} ms (ruta {ruta_max}), menor a la meta de 500 ms, y no hubo errores. "
    else:
        texto += (f"El p95 más alto fue de {p95_max:g} ms (ruta {ruta_max}) y {len(fuera)} ruta(s) quedaron fuera de la meta de 500 ms "
                  f"({', '.join(r for r, _, _ in fuera)}); se registra como brecha. ")
    texto += f"Con 10 usuarios simultáneos el p95 más alto fue de {p95_10:g} ms. "
    texto += ("La medición se hizo en el mismo equipo que el servidor y con datos sintéticos, por lo que no reemplaza una medición "
              "en el servidor del gimnasio.")
    L.append(texto + "\n")
    L.append("## 6. Limitaciones\n")
    L += ["- La prueba corre en el mismo equipo que el servidor (localhost): mide el servidor y la base de datos, no la red.",
          "- El equipo del grupo no es la Raspberry Pi donde correría en un gimnasio, así que los tiempos no se pueden trasladar directamente.",
          "- La base usa datos sintéticos de demostración.",
          "- Solo se miden peticiones de lectura (GET)."]
    (carpeta / "informe_prueba_carga.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print("\n" + "=" * 60)
    print("RESULTADO FINAL: " + ("CUMPLE" if cumple else "NO CUMPLE") + f" · p95 más alto con 1 usuario: {p95_max:g} ms ({ruta_max})")
    print(f"Listo. Revisa {carpeta / 'informe_prueba_carga.md'} y envía ese archivo para dejar el informe al día.")
    sys.exit(0 if cumple else 1)


if __name__ == "__main__":
    main()
