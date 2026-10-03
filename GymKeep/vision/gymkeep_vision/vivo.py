"""Conexion en vivo con la plataforma (`/api/v1/vision/camaras/{id}/...`).

Corre en su propio hilo para que la red nunca frene el analisis: el pipeline deja aqui el
ultimo estado (y, cada tanto, el ultimo cuadro) y el hilo los envia cuando le toca. Si la
API se cae, se descarta lo pendiente y se sigue intentando: lo que importa es lo mas reciente.

Ademas relee la configuracion de la camara cada pocos segundos: si alguien dibuja o edita la
zona de una maquina en el panel, el pipeline la aplica sin reiniciarse.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time

import httpx

log = logging.getLogger(__name__)


def buscar_camara(cliente: httpx.Client, codigo: str) -> dict:
    respuesta = cliente.get("/api/v1/vision/camaras")
    respuesta.raise_for_status()
    for camara in respuesta.json():
        if camara["codigo"] == codigo or str(camara["id"]) == codigo:
            return camara
    raise RuntimeError(f"No existe la camara '{codigo}' en GymKeep (crearla desde el panel o con POST /camaras/)")


def leer_configuracion(cliente: httpx.Client, camara_id: int) -> dict:
    respuesta = cliente.get(f"/api/v1/vision/camaras/{camara_id}/configuracion")
    respuesta.raise_for_status()
    return respuesta.json()


def huella(configuracion: dict) -> str:
    return hashlib.sha1(json.dumps(configuracion, sort_keys=True).encode()).hexdigest()


class PublicadorVivo:
    def __init__(
        self,
        cliente: httpx.Client,
        camara_id: int,
        *,
        cada_estado_s: float = 1.0,
        cada_cuadro_s: float = 2.0,
        cada_config_s: float = 5.0,
        huella_config: str | None = None,
    ):
        self.cliente = cliente
        self.camara_id = camara_id
        self.cada_estado_s = cada_estado_s
        self.cada_cuadro_s = cada_cuadro_s
        self.cada_config_s = cada_config_s

        self._lock = threading.Lock()
        self._estado: dict | None = None
        self._cuadro: bytes | None = None
        self._config_nueva: dict | None = None
        self._huella = huella_config
        self._ultimo_envio_cuadro = 0.0
        self._parar = threading.Event()
        self._errores = 0
        self.enviados = 0
        self._hilo = threading.Thread(target=self._bucle, name="gymkeep-vivo", daemon=True)
        self._hilo.start()

    # -- lado del pipeline (no bloquea nunca)

    def necesita_cuadro(self) -> bool:
        return time.monotonic() - self._ultimo_envio_cuadro >= self.cada_cuadro_s and self._cuadro is None

    def publicar(self, estado: dict, cuadro_jpeg: bytes | None = None) -> None:
        with self._lock:
            self._estado = estado
            if cuadro_jpeg is not None:
                self._cuadro = cuadro_jpeg

    def tomar_config_nueva(self) -> dict | None:
        with self._lock:
            nueva, self._config_nueva = self._config_nueva, None
        return nueva

    def cerrar(self) -> None:
        self._parar.set()
        self._hilo.join(timeout=5)

    # -- hilo de envio

    def _bucle(self) -> None:
        proximo_estado = proxima_config = time.monotonic()
        base = f"/api/v1/vision/camaras/{self.camara_id}"
        while not self._parar.wait(0.1):
            ahora = time.monotonic()
            with self._lock:
                estado = self._estado if ahora >= proximo_estado else None
                if estado is not None:
                    self._estado = None
                cuadro, self._cuadro = self._cuadro, None
            if estado is not None:
                proximo_estado = ahora + self.cada_estado_s
                self._enviar(lambda: self.cliente.post(f"{base}/vivo", json=estado))
            if cuadro is not None:
                self._ultimo_envio_cuadro = ahora
                self._enviar(
                    lambda: self.cliente.put(f"{base}/cuadro", content=cuadro, headers={"Content-Type": "image/jpeg"})
                )
            if ahora >= proxima_config:
                proxima_config = ahora + self.cada_config_s
                self._revisar_config()

    def _enviar(self, peticion) -> None:
        try:
            respuesta = peticion()
            respuesta.raise_for_status()
            self.enviados += 1
            if self._errores:
                log.info("Conexion con la plataforma recuperada")
            self._errores = 0
        except httpx.HTTPError as exc:
            self._errores += 1
            if self._errores in (1, 10) or self._errores % 100 == 0:
                log.warning("No se pudo enviar el estado en vivo (%s); se reintenta", exc)

    def _revisar_config(self) -> None:
        try:
            configuracion = leer_configuracion(self.cliente, self.camara_id)
        except httpx.HTTPError:
            return
        nueva_huella = huella(configuracion)
        if nueva_huella != self._huella:
            self._huella = nueva_huella
            with self._lock:
                self._config_nueva = configuracion
