"""Traduce los eventos de uso al documento que recibe `POST /api/v1/eventos-ia/`
(`app/schemas/ai_event.py::EventoIACreate`) y los entrega a sus destinos: un archivo
JSONL (siempre) y la API de GymKeep (opcional)."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

import httpx

from gymkeep_vision import __version__, tiempo
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
            "t_max_s": cfg.uso.t_max_s,
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
        "timestamp": tiempo.marca(inicio_video, ev.t),
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
    """Registro local de todos los eventos: permite reenviarlos despues con `enviar`.
    Abre en modo append: reiniciar el pipeline no borra el historial."""

    def __init__(self, ruta: Path):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta = ruta
        self._archivo = ruta.open("a", encoding="utf-8")

    def enviar(self, evento: dict) -> None:
        self._archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
        self._archivo.flush()

    def cerrar(self) -> None:
        self._archivo.close()


# Respuestas 4xx que no indican un evento mal formado sino un problema pasajero o de
# configuracion (clave del pipeline, limite de peticiones): se reintentan, no se descartan.
_REINTENTABLES = {401, 403, 408, 425, 429}


class DestinoAPI:
    """Envia los eventos al backend sin frenar el analisis: `enviar` solo encola y un hilo
    se encarga de la red. Los reintentos son seguros porque el backend es idempotente por
    `event_uuid` (un reenvio devuelve el evento ya guardado).

    Si la API no responde, el evento pasa a `atrasados` y se guarda en `ruta_pendientes`
    (JSONL, un evento por linea). Los atrasados se reintentan en orden, con espera creciente
    (1, 2, 4... hasta `espera_max_s` s), y los eventos nuevos esperan detras de ellos para no
    alterar el orden. Al arrancar se leen los pendientes que dejo una corrida anterior."""

    def __init__(
        self,
        cliente: httpx.Client,
        reintentos: int = 3,
        *,
        ruta_pendientes: Path | None = None,
        espera_inicial_s: float = 1.0,
        espera_max_s: float = 30.0,
        pausa_s: float = 0.5,
    ):
        self.cliente = cliente
        self.reintentos = reintentos
        self.ruta_pendientes = ruta_pendientes
        self.espera_inicial_s = espera_inicial_s
        self.espera_max_s = espera_max_s
        self.pausa_s = pausa_s
        self.enviados = 0
        self.fallidos: list[dict] = []  # rechazados por la API (no se reintentan)

        self._cola: queue.Queue = queue.Queue()
        self._atrasados: deque[dict] = deque()
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._limite = float("inf")  # instante (monotonic) hasta el cual se drena al cerrar
        self._en_vuelo: dict | None = None
        self._cargar_pendientes()
        self._hilo = threading.Thread(target=self._bucle, name="gymkeep-eventos", daemon=True)
        self._hilo.start()

    @property
    def pendientes(self) -> int:
        """Eventos que todavia no llegan a la API (en cola o atrasados)."""
        return self._cola.qsize() + len(self._atrasados) + (1 if self._en_vuelo is not None else 0)

    # -- lado del pipeline (no bloquea nunca)

    def enviar(self, evento: dict) -> None:
        self._cola.put(evento)

    def cerrar(self, espera_s: float = 15.0) -> None:
        """Intenta entregar lo pendiente durante a lo mas `espera_s`; lo que no alcance a
        salir queda en el archivo de pendientes para la proxima corrida."""
        self._limite = time.monotonic() + espera_s
        self._parar.set()
        self._hilo.join(timeout=espera_s + 12)  # 12 s: un envio en curso puede tardar hasta el timeout
        with self._lock:
            restantes = ([self._en_vuelo] if self._en_vuelo is not None else []) + self._vaciar_cola()
            if restantes or self._atrasados:
                for evento in restantes:
                    if evento not in self._atrasados:
                        self._atrasar(evento)
                log.warning("%d eventos quedaron pendientes de envio (%s)", len(self._atrasados), self.ruta_pendientes)

    # -- envio directo (sin cola): lo usa el comando `enviar`

    def enviar_ahora(self, evento: dict) -> dict | None:
        for intento in range(1, self.reintentos + 1):
            resultado, cuerpo = self._intentar(evento)
            if resultado == "ok":
                return cuerpo
            if resultado == "rechazado":
                break
            log.warning("Reintento %d/%d", intento, self.reintentos)
            time.sleep(self.pausa_s * intento)
        self.fallidos.append(evento)
        return None

    # -- hilo de envio

    def _intentar(self, evento: dict) -> tuple[str, dict | None]:
        """Un intento de envio: ('ok', respuesta) | ('rechazado', None) | ('reintentar', None)."""
        try:
            respuesta = self.cliente.post("/api/v1/eventos-ia/", json=evento)
        except httpx.TransportError as exc:
            log.warning("API no responde (%s)", exc)
            return "reintentar", None
        if respuesta.status_code < 300:
            self.enviados += 1
            return "ok", respuesta.json()
        if respuesta.status_code < 500 and respuesta.status_code not in _REINTENTABLES:
            log.error("La API rechazo %s: %s", evento["evento"]["tipo"], respuesta.text)
            return "rechazado", None
        log.warning("Error %d en la API", respuesta.status_code)
        return "reintentar", None

    def _bucle(self) -> None:
        espera = self.espera_inicial_s
        while True:
            if time.monotonic() >= self._limite:
                return  # cerrar() se encarga de dejar lo que falte en el archivo
            with self._lock:
                # Los eventos nuevos van detras de los atrasados: se conserva el orden.
                if self._atrasados:
                    for evento in self._vaciar_cola():
                        self._atrasar(evento)
                    self._en_vuelo = self._atrasados[0]
                    atrasado = True
                else:
                    atrasado = False
                    try:
                        self._en_vuelo = self._cola.get_nowait()
                    except queue.Empty:
                        self._en_vuelo = None
                        if self._parar.is_set():
                            return
            if self._en_vuelo is None:
                self._parar.wait(0.2)
                continue

            evento = self._en_vuelo
            resultado = "reintentar"
            # Un atrasado se prueba una vez por vuelta (el bucle ya espera entre vueltas).
            for intento in range(1, (1 if atrasado else self.reintentos) + 1):
                resultado, _ = self._intentar(evento)
                if resultado != "reintentar":
                    break
                time.sleep(self.pausa_s * intento)
            with self._lock:
                self._en_vuelo = None
                if resultado == "reintentar":
                    if not atrasado:
                        self._atrasar(evento)
                elif atrasado:
                    self._atrasados.popleft()
                    self._reescribir_pendientes()
                if resultado == "rechazado":
                    self.fallidos.append(evento)
            if resultado == "reintentar":
                # Con la API caida se espera cada vez mas; al cerrar solo una pausa corta.
                pausa = min(espera, 0.5) if self._parar.is_set() else espera
                time.sleep(pausa)
                espera = min(self.espera_max_s, espera * 2)
            else:
                espera = self.espera_inicial_s

    def _vaciar_cola(self) -> list[dict]:
        eventos = []
        while True:
            try:
                eventos.append(self._cola.get_nowait())
            except queue.Empty:
                return eventos

    # -- pendientes en disco

    def _atrasar(self, evento: dict) -> None:
        self._atrasados.append(evento)
        if self.ruta_pendientes is not None:
            self.ruta_pendientes.parent.mkdir(parents=True, exist_ok=True)
            with self.ruta_pendientes.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")

    def _reescribir_pendientes(self) -> None:
        if self.ruta_pendientes is None:
            return
        if not self._atrasados:
            self.ruta_pendientes.unlink(missing_ok=True)
            return
        tmp = self.ruta_pendientes.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in self._atrasados), encoding="utf-8")
        tmp.replace(self.ruta_pendientes)

    def _cargar_pendientes(self) -> None:
        if self.ruta_pendientes is None or not self.ruta_pendientes.exists():
            return
        for linea in self.ruta_pendientes.read_text(encoding="utf-8").splitlines():
            try:
                if linea.strip():
                    self._atrasados.append(json.loads(linea))
            except json.JSONDecodeError:
                log.warning("Linea danada en %s: se omite", self.ruta_pendientes)
        if self._atrasados:
            log.info("%d eventos pendientes de una corrida anterior: se reintentan", len(self._atrasados))


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
