"""Zonas iniciales de una camara (preset) y espera a que la API este lista.

Sirve para que el Docker de vision arranque con algo que ver: un JSON con las zonas de las
maquinas (poligonos normalizados 0..1) se aplica a la camara de GymKeep por la API, igual que
si se hubieran dibujado en el panel. Se aplica UNA vez (queda una marca en la carpeta de
salida): despues mandan las zonas que se editen en el panel.

Un preset puede traer ademas `crear_camara` (nombre, sucursal_codigo, zona: la camara y su zona se
crean si faltan) y `parametros` (T_on, T_off, confianza minima, gracia y escala de tiempo de esa
camara). Asi cada video de la demo se ve con la configuracion con que se midio.
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


def _normalizar(texto: str) -> str:
    return " ".join(str(texto).lower().split())


def _listar(cliente: httpx.Client, ruta: str, **params) -> list[dict]:
    respuesta = cliente.get(ruta, params={"limit": 500, **params})
    respuesta.raise_for_status()
    return respuesta.json()


def _listar_todos(cliente: httpx.Client, ruta: str, **params) -> list[dict]:
    """Todas las filas de un listado paginado. La API acepta como maximo 500 por pagina (mas da 422)."""
    filas: list[dict] = []
    while True:
        pagina = _listar(cliente, ruta, skip=len(filas), **params)
        filas.extend(pagina)
        if len(pagina) < 500:
            return filas


def _buscar_sucursal(cliente: httpx.Client, codigo: str | None) -> dict:
    """La sucursal del preset por su codigo; si no existe pero hay una sola, esa."""
    sucursales = _listar(cliente, "/api/v1/sucursales/")
    for sucursal in sucursales:
        if codigo and sucursal.get("codigo") == codigo:
            return sucursal
    if len(sucursales) == 1:
        log.warning("No existe la sucursal '%s'; se usa la unica que hay (%s)", codigo, sucursales[0].get("codigo"))
        return sucursales[0]
    raise RuntimeError(f"No existe la sucursal '{codigo}' en GymKeep (y hay {len(sucursales)}: no se sabe cual usar)")


def _asegurar_zona(cliente: httpx.Client, sucursal_id: int, nombre: str | None) -> int | None:
    """Id de la zona `nombre` de la sucursal; la crea si no existe. Sin nombre, sin zona."""
    if not nombre:
        return None
    for zona in _listar(cliente, "/api/v1/zonas/", sucursal_id=sucursal_id):
        if _normalizar(zona["nombre"]) == _normalizar(nombre):
            return zona["id"]
    creada = cliente.post("/api/v1/zonas/", json={"sucursal_id": sucursal_id, "nombre": nombre})
    creada.raise_for_status()
    log.info("Zona registrada en GymKeep: %s (id %s)", nombre, creada.json()["id"])
    return creada.json()["id"]


def asegurar_camara(cliente: httpx.Client, codigo: str, datos: dict) -> dict:
    """La camara `codigo` de GymKeep. Si no existe y el preset trae `crear_camara`, la crea (con
    su sucursal y zona); si no trae esa clave, falla igual que antes (hay que crearla en el panel)."""
    from gymkeep_vision import vivo

    try:
        return vivo.buscar_camara(cliente, codigo)
    except RuntimeError:
        nueva = datos.get("crear_camara")
        if not nueva:
            raise
    sucursal = _buscar_sucursal(cliente, nueva.get("sucursal_codigo"))
    zona_id = _asegurar_zona(cliente, sucursal["id"], nueva.get("zona"))
    creada = cliente.post(
        "/api/v1/camaras/",
        json={
            "codigo": codigo,
            "nombre": nueva.get("nombre", codigo),
            "sucursal_id": sucursal["id"],
            "zona_id": zona_id,
            "equipo_ids": [],
        },
    )
    creada.raise_for_status()
    log.info("Camara registrada en GymKeep: %s (id %s)", codigo, creada.json()["id"])
    return vivo.buscar_camara(cliente, codigo)


def aplicar(cliente: httpx.Client, camara: dict, datos: dict, *, crear_equipos: bool = True) -> int:
    """Guarda en GymKeep la zona de cada maquina del preset. Devuelve cuantas aplico.

    Una maquina que no existe en el inventario de la sucursal se crea (con la zona de la
    camara) salvo `crear_equipos=False`, en cuyo caso se omite con un aviso."""
    equipos = {e["codigo_activo"]: e for e in _listar_todos(cliente, "/api/v1/equipamiento/", sucursal_id=camara["sucursal_id"])}
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
    parametros = datos.get("parametros")
    if parametros:
        guardados = cliente.put(f"/api/v1/vision/camaras/{camara['id']}/parametros", json=parametros)
        guardados.raise_for_status()
        log.info("Parametros de %s: %s", camara["codigo"], parametros)
    return aplicadas
