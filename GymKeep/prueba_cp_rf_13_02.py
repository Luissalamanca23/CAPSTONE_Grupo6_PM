"""Repite el caso CP-RF-13-02 (filtros de incidencias) contra la API en marcha. Solo LEE: no crea ni borra nada.

Uso (PowerShell, con la demo o el sistema levantados):
    python prueba_cp_rf_13_02.py                     # usa http://127.0.0.1:8088 (demo local)
    python prueba_cp_rf_13_02.py http://127.0.0.1:8000

Pide el RUN y la clave de una cuenta del panel (la clave no se muestra ni se guarda).
Deja el resultado en CP-RF-13-02_repeticion.txt, junto a este archivo.
"""

import getpass
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from http.cookiejar import CookieJar
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8088").rstrip("/")
API = BASE + "/api/v1"
SALIDA = Path(__file__).resolve().parent / "CP-RF-13-02_repeticion.txt"

abre = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar())).open
lineas = []


def decir(texto=""):
    print(texto)
    lineas.append(texto)


def pedir(ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(API + ruta, data=datos, headers={"Content-Type": "application/json"})
    with abre(peticion, timeout=30) as r:
        return json.loads(r.read() or "null"), r.headers


def resultado(ok, texto):
    decir(("  [OK]    " if ok else "  [FALLA] ") + texto)
    return ok


run = input("RUN: ").strip()
clave = getpass.getpass("Clave (no se muestra): ")
try:
    pedir("/auth/login", {"run": run, "clave": clave})
except urllib.error.HTTPError as e:
    sys.exit(f"No se pudo iniciar sesion (HTTP {e.code}). Revisa el RUN y la clave.")
except urllib.error.URLError as e:
    sys.exit(f"No se pudo conectar con {BASE}: {e.reason}")

decir(f"CP-RF-13-02 repetido el {datetime.now():%d-%m-%Y %H:%M} contra {BASE} (solo lectura)")
decir()
fallas = 0

todas, h = pedir("/incidencias/?limit=500")
total = int(h["X-Total-Count"])
decir(f"Total de incidencias sin filtros: {total}")
if total == 0:
    sys.exit("No hay incidencias para probar los filtros.")

# Paso 4 del caso original (el que fallo): una sucursal que no existe debe devolver 0.
lista, h = pedir("/incidencias/?sucursal_id=999999")
decir("Sucursal inexistente (sucursal_id=999999):")
fallas += not resultado(len(lista) == 0 and h["X-Total-Count"] == "0", f"devolvio {len(lista)} incidencias (esperado: 0), X-Total-Count={h['X-Total-Count']}")

# Cada sucursal existente: sus incidencias deben sumar el total (todos los equipos pertenecen a una sucursal).
sucursales, _ = pedir("/sucursales/")
suma = 0
decir("Por sucursal existente:")
for s in sucursales:
    _, h = pedir(f"/incidencias/?sucursal_id={s['id']}&limit=1")
    n = int(h["X-Total-Count"])
    suma += n
    decir(f"  sucursal {s['id']} ({s.get('codigo', '?')}): {n} incidencias")
fallas += not resultado(suma == total, f"la suma por sucursal ({suma}) {'coincide' if suma == total else 'NO coincide'} con el total ({total})")

# Pasos 2 y 3: filtros por equipo y por prioridad devuelven solo lo que corresponde.
eq = todas[0]["equipo_id"]
lista, h = pedir(f"/incidencias/?equipo_id={eq}&limit=500")
decir(f"Filtro por equipo (equipo_id={eq}):")
fallas += not resultado(len(lista) > 0 and all(i["equipo_id"] == eq for i in lista), f"{len(lista)} incidencias, todas del equipo {eq}")
for prio in sorted({i["prioridad"] for i in todas}):
    lista, h = pedir(f"/incidencias/?prioridad={prio}&limit=500")
    esperado = int(h["X-Total-Count"])
    decir(f"Filtro por prioridad ({prio}):")
    fallas += not resultado(len(lista) > 0 and all(i["prioridad"] == prio for i in lista), f"{esperado} incidencias, todas con prioridad {prio}")

decir()
decir("RESULTADO: " + ("APROBADO: los filtros devuelven solo lo que corresponde (DEF-01 corregido)." if fallas == 0 else f"FALLIDO: {fallas} comprobacion(es) fallaron."))
SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
print(f"\nResultado guardado en {SALIDA.name}")
sys.exit(1 if fallas else 0)
