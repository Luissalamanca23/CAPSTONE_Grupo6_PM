"""Traduce los eventos de uso al documento que recibe `POST /api/v1/eventos-ia/`
(`app/schemas/ai_event.py::EventoIACreate`) y los entrega a sus destinos: un archivo
JSONL (siempre) y la API de GymKeep (opcional)."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from gymkeep_vision import __version__
from gymkeep_vision.config import Config, ConfigMaquina
from gymkeep_vision.sesiones import EventoUso
from gymkeep_vision.zonas import Deteccion

log = logging.getLogger(__name__)


def construir_evento(
    ev: EventoUso,
    *,
    cfg: Config,
    maquina: ConfigMaquina,
    inicio_video: datetime,
    detecciones: list[Deteccion],
    snapshot_url: str | None,
    fuente: str,
) -> dict:
    sesion = ev.sesion
    metadata = {
        "pipeline": f"gymkeep-vision/{__version__}",
        "sesion_ref": sesion.ref,
        "maquina": maquina.nombre,
        "codigo_activo": maquina.codigo_activo,
        "camara_codigo": cfg.camara.codigo,
        "fuente": fuente,
        "t_s": round(ev.t, 2),  # segundos reales desde el inicio del video
        "t_emision_s": round(ev.t_emision, 2),
        "parametros": {
            "t_on_s": cfg.uso.t_on_s,
            "t_off_s": cfg.uso.t_off_s,
            "confianza_min": cfg.confianza_min,
            "criterio_zona": maquina.criterio or cfg.criterio_zona,
        },
    }
    if ev.tipo == "fin_uso":
        metadata.update(
            duracion_segundos=round(sesion.duracion_s, 1),
            presencia_segundos=round(sesion.presencia_s, 1),
            pausas=sesion.pausas,
            pausa_max_segundos=round(sesion.pausa_max_s, 1),
            personas_max=sesion.personas_max,
            cantidad_eventos=sesion.eventos,
            cierre=sesion.cierre,
        )

    return {
        "event_uuid": str(uuid.uuid4()),
        "timestamp": (inicio_video + timedelta(seconds=ev.t)).isoformat(),
        "empresa_id": cfg.camara.empresa_id,
        "sucursal_id": cfg.camara.sucursal_id,
        "zona_id": cfg.camara.zona_id,
        "camara_id": cfg.camara.id,
        "equipo_id": maquina.equipo_id,
        "sesion_uso_id": None,  # lo asigna el backend al consolidar la sesion
        "modelo": {"id": cfg.modelo.id, "nombre": cfg.modelo.nombre, "version": cfg.modelo.version},
        "evento": {
            "tipo": ev.tipo,
            "confidence": round(ev.confianza, 4) if ev.confianza is not None else None,
        },
        "detecciones": [
            {
                "clase": "persona",
                "confidence": round(d.confianza, 4),
                "bbox": [round(v) for v in d.bbox],
                "track_id": d.track_id,
            }
            for d in detecciones
        ],
        "tracking": {
            "persona_track_ids": sorted(sesion.track_ids),
            "tiempo_interaccion_segundos": round(sesion.duracion_s, 1),
        },
        "evidencia": {"snapshot_url": snapshot_url, "clip_url": None},
        "metadata": metadata,
    }


class DestinoJSONL:
    """Registro local de todos los eventos: permite reenviarlos despues con `enviar`."""

    def __init__(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta = ruta
        self._archivo = ruta.open("w", encoding="utf-8")

    def enviar(self, evento: dict) -> None:
        self._archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
        self._archivo.flush()

    def cerrar(self) -> None:
        self._archivo.close()


class DestinoAPI:
    """Envia los eventos al backend. Los reintentos son seguros porque el backend es
    idempotente por `event_uuid` (un reenvio devuelve el evento ya guardado)."""

    def __init__(self, cliente: httpx.Client, reintentos: int = 3):
        self.cliente = cliente
        self.reintentos = reintentos
        self.enviados = 0
        self.fallidos: list[dict] = []

    def enviar(self, evento: dict) -> dict | None:
        for intento in range(1, self.reintentos + 1):
            try:
                respuesta = self.cliente.post("/api/v1/eventos-ia/", json=evento)
            except httpx.TransportError as exc:
                log.warning("API no responde (%s), intento %d/%d", exc, intento, self.reintentos)
            else:
                if respuesta.status_code < 300:
                    self.enviados += 1
                    return respuesta.json()
                if respuesta.status_code < 500:
                    log.error("La API rechazo %s: %s", evento["evento"]["tipo"], respuesta.text)
                    break
                log.warning("Error %d en la API, intento %d/%d", respuesta.status_code, intento, self.reintentos)
            time.sleep(0.5 * intento)
        self.fallidos.append(evento)
        return None

    def cerrar(self) -> None:
        pass


def _buscar(items: list[dict], **filtro) -> dict | None:
    return next((i for i in items if all(i.get(k) == v for k, v in filtro.items())), None)


def resolver_ids(cliente: httpx.Client, cfg: Config, *, registrar: bool = False) -> None:
    """Completa en `cfg` los IDs de GymKeep a partir de los codigos del YAML
    (sucursal, zona, `camaras.codigo`, `equipos.codigo_activo`). Con `registrar=True`
    crea en GymKeep los equipos y la camara que falten, con sus ROI asociadas."""
    cam = cfg.camara

    def get(ruta: str, **params) -> list[dict]:
        respuesta = cliente.get(ruta, params={"limit": 1000, **params})
        respuesta.raise_for_status()
        return respuesta.json()

    if cam.sucursal_id is None:
        sucursal = _buscar(get("/api/v1/sucursales/"), codigo=cam.sucursal_codigo)
        if sucursal is None:
            raise RuntimeError(f"No existe la sucursal '{cam.sucursal_codigo}' en GymKeep")
        cam.sucursal_id, cam.empresa_id = sucursal["id"], sucursal["empresa_id"]

    if cam.zona_id is None and cam.zona_nombre:
        zona = _buscar(get("/api/v1/zonas/", sucursal_id=cam.sucursal_id), nombre=cam.zona_nombre)
        if zona is None:
            raise RuntimeError(f"No existe la zona '{cam.zona_nombre}' en la sucursal {cam.sucursal_codigo}")
        cam.zona_id = zona["id"]

    equipos = get("/api/v1/equipamiento/", sucursal_id=cam.sucursal_id)
    for maquina in cfg.maquinas:
        if maquina.equipo_id is not None:
            continue
        equipo = _buscar(equipos, codigo_activo=maquina.codigo_activo)
        if equipo is None and registrar:
            respuesta = cliente.post(
                "/api/v1/equipamiento/",
                json={
                    "sucursal_id": cam.sucursal_id,
                    "zona_id": cam.zona_id,
                    "codigo_activo": maquina.codigo_activo,
                    "nombre": maquina.nombre,
                    "categoria": maquina.categoria,
                    "observaciones": "Registrado por gymkeep-vision (demo de medicion de uso).",
                },
            )
            respuesta.raise_for_status()
            equipo = respuesta.json()
            log.info("Equipo registrado en GymKeep: %s (id %s)", maquina.codigo_activo, equipo["id"])
        if equipo is None:
            raise RuntimeError(
                f"El equipo '{maquina.codigo_activo}' no existe en GymKeep (usar --registrar para crearlo)"
            )
        maquina.equipo_id = equipo["id"]

    if cam.id is None:
        camara = _buscar(get("/api/v1/camaras/", sucursal_id=cam.sucursal_id), codigo=cam.codigo)
        if camara is None and registrar:
            respuesta = cliente.post(
                "/api/v1/camaras/",
                json={
                    "codigo": cam.codigo,
                    "nombre": cam.nombre or cam.codigo,
                    "sucursal_id": cam.sucursal_id,
                    "zona_id": cam.zona_id,
                    "equipo_ids": [m.equipo_id for m in cfg.maquinas],
                },
            )
            respuesta.raise_for_status()
            camara = respuesta.json()
            log.info("Camara registrada en GymKeep: %s (id %s)", cam.codigo, camara["id"])
        if camara is None:
            raise RuntimeError(f"La camara '{cam.codigo}' no existe en GymKeep (usar --registrar para crearla)")
        cam.id = camara["id"]

    # El modelo es opcional en el evento, pero registrarlo deja trazado que version del
    # pipeline genero cada sesion (modelos_ia).
    mod = cfg.modelo
    if mod.id is None:
        modelo = _buscar(get("/api/v1/modelos-ia/"), nombre=mod.nombre, version=mod.version)
        if modelo is None and registrar:
            respuesta = cliente.post(
                "/api/v1/modelos-ia/",
                json={
                    "nombre": mod.nombre,
                    "version": mod.version,
                    "framework": f"Ultralytics {Path(mod.pesos).stem} + {Path(mod.tracker).stem}",
                    "tipo_modelo": "deteccion_tracking_uso",
                    "clases": ["persona"],
                },
            )
            respuesta.raise_for_status()
            modelo = respuesta.json()
        if modelo is not None:
            mod.id = modelo["id"]


def completar_ids(evento: dict, cfg: Config) -> dict:
    """Pone en un evento ya generado los IDs resueltos contra la API (para `enviar`)."""
    maquina = next(m for m in cfg.maquinas if m.codigo_activo == evento["metadata"]["codigo_activo"])
    return {
        **evento,
        "empresa_id": cfg.camara.empresa_id,
        "sucursal_id": cfg.camara.sucursal_id,
        "zona_id": cfg.camara.zona_id,
        "camara_id": cfg.camara.id,
        "equipo_id": maquina.equipo_id,
        "modelo": {**evento["modelo"], "id": cfg.modelo.id},
    }
