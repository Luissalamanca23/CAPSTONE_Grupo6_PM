"""Prueba de carga de la API de GymKeep (criterio: p95 < 500 ms).

Solo usa la biblioteca estandar de Python (no hay que instalar nada).

Ejemplo (PowerShell, desde la carpeta GymKeep, con la API en http://localhost:8000):

    $env:GYMKEEP_CLAVE = "1234"
    python prueba_carga.py --run 12345678-9 --peticiones 100 --concurrencia 1 10

Hace login una sola vez (el login tiene limite de intentos), calienta cada ruta con
10 peticiones que no se cuentan y despues mide `--peticiones` peticiones por ruta y por
nivel de concurrencia. El p95 usa el metodo del rango mas cercano: con 100 peticiones es
el valor n.o 95 de la lista ordenada de menor a mayor.
"""

import argparse
import csv
import http.cookiejar
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

RUTAS = [
    "/api/v1/estadisticas/",
    "/api/v1/equipamiento/",
    "/api/v1/incidencias/",
    "/api/v1/mantenimientos/",
    "/api/v1/sesiones-uso/horometro",
    "/api/v1/sucursales/",
]
UMBRAL_MS = 500.0


def percentil(valores, p):
    """Rango mas cercano: el valor n.o ceil(p/100 * n) de la lista ordenada."""
    orden = sorted(valores)
    return orden[max(0, math.ceil(p / 100 * len(orden)) - 1)]


def crear_cliente():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def login(cliente, base, run, clave):
    cuerpo = json.dumps({"run": run, "clave": clave}).encode()
    req = urllib.request.Request(
        base + "/api/v1/auth/login", data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    with cliente.open(req, timeout=30) as r:
        r.read()


def una_peticion(cliente, url):
    """Devuelve (milisegundos, ok). El tiempo incluye leer toda la respuesta."""
    t0 = time.perf_counter()
    try:
        with cliente.open(url, timeout=30) as r:
            r.read()
            ok = r.status == 200
    except (urllib.error.URLError, OSError):
        ok = False
    return (time.perf_counter() - t0) * 1000, ok


def medir(cliente, url, n, concurrencia):
    with ThreadPoolExecutor(max_workers=concurrencia) as pool:
        resultados = list(pool.map(lambda _: una_peticion(cliente, url), range(n)))
    ms = [t for t, ok in resultados if ok]
    errores = sum(1 for _, ok in resultados if not ok)
    return ms, errores


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000", help="direccion de la API")
    ap.add_argument("--run", required=True, help="RUN del usuario del panel (admin o tecnico)")
    ap.add_argument("--clave", default=os.environ.get("GYMKEEP_CLAVE"), help="o variable GYMKEEP_CLAVE")
    ap.add_argument("--peticiones", type=int, default=100, help="peticiones medidas por ruta (100)")
    ap.add_argument("--concurrencia", type=int, nargs="+", default=[1], help="usuarios simultaneos, ej. 1 10")
    ap.add_argument("--token", help="token de un QR, para medir tambien GET /equipamiento/qr/{token} (publica)")
    ap.add_argument("--salida", default=None, help="archivo CSV de resultados")
    a = ap.parse_args()
    if not a.clave:
        sys.exit("Falta la clave: usa --clave o la variable de entorno GYMKEEP_CLAVE.")

    base = a.url.rstrip("/")
    cliente = crear_cliente()
    try:
        login(cliente, base, a.run, a.clave)
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"No se pudo iniciar sesion en {base}: {e}")

    rutas = list(RUTAS)
    if a.token:
        rutas.append(f"/api/v1/equipamiento/qr/{a.token}")

    salida = a.salida or f"resultados_carga_{datetime.now():%Y%m%d_%H%M%S}.csv"
    filas, todo_ok = [], True
    nivel_base = 1 if 1 in a.concurrencia else min(a.concurrencia)  # el criterio se decide con este nivel; los demas informan
    ok_otros = True
    print(f"\nPrueba de carga {datetime.now():%Y-%m-%d %H:%M}  |  {base}  |  {a.peticiones} peticiones por ruta")
    for conc in a.concurrencia:
        print(f"\nUsuarios simultaneos: {conc}")
        print(f"{'ruta':<36}{'err':>4}{'min':>8}{'p50':>8}{'p95':>8}{'p99':>8}{'max':>8}  p95<{UMBRAL_MS:.0f} ms")
        for ruta in rutas:
            url = base + ruta
            medir(cliente, url, 10, 1)  # calentamiento: no cuenta
            ms, errores = medir(cliente, url, a.peticiones, conc)
            if not ms:
                print(f"{ruta:<36}{errores:>4}  todas las peticiones fallaron")
                if conc == nivel_base: todo_ok = False
                else: ok_otros = False
                continue
            p95 = percentil(ms, 95)
            cumple = p95 < UMBRAL_MS and errores == 0
            if conc == nivel_base: todo_ok &= cumple
            else: ok_otros &= cumple
            fila = {
                "concurrencia": conc, "ruta": ruta, "peticiones": a.peticiones, "errores": errores,
                "min_ms": round(min(ms), 1), "p50_ms": round(statistics.median(ms), 1),
                "p95_ms": round(p95, 1), "p99_ms": round(percentil(ms, 99), 1),
                "max_ms": round(max(ms), 1), "cumple": "SI" if cumple else "NO",
            }
            filas.append(fila)
            print(f"{ruta:<36}{errores:>4}{fila['min_ms']:>8}{fila['p50_ms']:>8}{fila['p95_ms']:>8}"
                  f"{fila['p99_ms']:>8}{fila['max_ms']:>8}  {fila['cumple']}")
    if filas:
        with open(salida, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        print(f"\nResultados guardados en {salida}")
    if len(a.concurrencia) > 1:
        print(f"Con mas de {nivel_base} usuario(s) (solo informativo): " + ("todas las rutas con p95 < 500 ms" if ok_otros else "hay rutas con p95 >= 500 ms o con errores"))
    print(f"RESULTADO con {nivel_base} usuario(s): " + ("CUMPLE (todas las rutas con p95 < 500 ms y 0 errores)" if todo_ok else "NO CUMPLE en al menos una ruta"))
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
