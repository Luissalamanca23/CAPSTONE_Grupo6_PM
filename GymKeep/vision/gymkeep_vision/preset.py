"""Zonas iniciales de una camara (preset) y espera a que la API este lista.

Sirve para que el Docker de vision arranque con algo que ver: un JSON con las zonas de las
maquinas (poligonos normalizados 0..1) se aplica a la camara de GymKeep por la API, igual que
si se hubieran dibujado en el panel. Se aplica UNA vez (queda una marca en la carpeta de
salida): despues mandan las zonas que se editen en el panel.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)


def esperar_api(cliente: httpx.Client, hasta_s: float) -> None:
    """Espera (hasta `hasta_s` segundos) a que la API responda; el contenedor de la API tarda
    en arrancar (base de datos, migraciones) aunque `depends_on` ya lo de por iniciado."""
    if hasta_s <= 0:
        return
    limite = time.monotonic() + hasta_s
    avisado = False
    while True:
        try:
            if cliente.get("/api/v1/vision/camaras").status_code < 500:
                if avisado:
                    log.info("API lista")
                return
        except httpx.HTTPError as exc:
            ultimo = exc
        else:
            ultimo = "respuesta 5xx"
        if time.monotonic() >= limite:
            raise RuntimeError(f"La API no responde en {cliente.base_url} tras {hasta_s:.0f} s ({ultimo})")
        if not avisado:
            log.info("Esperando a la API en %s ...", cliente.base_url)
            avisado = True
        time.sleep(2)


def leer_preset(ruta: Path) -> dict:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if not datos.get("maquinas"):
        raise ValueError(f"{ruta}: falta la lista 'maquinas'")
    return datos


def aplicar(cliente: httpx.Client, camara: dict, datos: dict, *, crear_equipos: bool = True) -> int:
    """Guarda en GymKeep la zona de cada maquina del preset. Devuelve cuantas aplico.

    Una maquina que no existe en el inventario de la sucursal se crea (con la zona de la
    camara) salvo `crear_equipos=False`, en cuyo caso se omite con un aviso."""
    respuesta = cliente.get("/api/v1/equipamiento/", params={"sucursal_id": camara["sucursal_id"], "limit": 1000})
    respuesta.raise_for_status()
    equipos = {e["codigo_activo"]: e for e in respuesta.json()}
    aplicadas = 0
    for maquina in datos["maquinas"]:
        codigo = maquina["codigo_activo"]
        equipo = equipos.get(codigo)
        if equipo is None and crear_equipos:
            creado = cliente.post(
                "/api/v1/equipamiento/",
                json={
                    "sucursal_id": camara["sucursal_id"],
                    "zona_id": camara.get("zona_id"),
                    "codigo_activo": codigo,
                    "nombre": maquina.get("nombre", codigo),
                    "categoria": maquina.get("categoria", "cardio"),
                    "observaciones": "Registrado por gymkeep-vision (zonas iniciales de la demo).",
                },
            )
            creado.raise_for_status()
            equipo = creado.json()
            log.info("Equipo registrado en GymKeep: %s (id %s)", codigo, equipo["id"])
        if equipo is None:
            log.warning("El equipo %s no existe en GymKeep: se omite su zona", codigo)
            continue
        guardada = cliente.put(
            f"/api/v1/vision/camaras/{camara['id']}/maquinas/{equipo['id']}", json={"puntos": maquina["puntos"]}
        )
        guardada.raise_for_status()
        aplicadas += 1
        log.info("Zona de %s (%s) guardada en %s", codigo, maquina.get("nombre", ""), camara["codigo"])
    return aplicadas
