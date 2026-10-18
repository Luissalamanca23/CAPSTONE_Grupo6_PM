"""Lectura de una camara en vivo que sobrevive a cortes (RTSP caido, cable suelto, reinicio
de la camara). Un archivo de video termina cuando se acaba; una camara no: si deja de
entregar cuadros se vuelve a abrir la conexion, con esperas crecientes (1, 2, 4... hasta 30 s).

No sabe nada de YOLO ni de sesiones: solo entrega cuadros y dice cuanto tiempo lleva sin
recibir uno, para que el pipeline decida cuando dar por perdida la senal (ver `Pipeline`).
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


class LectorVivo:
    """Envuelve un `cv2.VideoCapture` (o cualquier objeto con `read`, `release`, `isOpened`).

    `abrir` es una funcion sin argumentos que crea una captura nueva. `leer()` nunca duerme:
    si esta esperando para reintentar, devuelve (False, None) de inmediato."""

    def __init__(self, abrir, captura, *, espera_inicial_s: float = 1.0, espera_max_s: float = 30.0, reloj=time.monotonic):
        self.abrir = abrir
        self.captura = captura
        self.espera_inicial_s = espera_inicial_s
        self.espera_max_s = espera_max_s
        self.reloj = reloj
        self.reconexiones = 0
        self.ultimo_cuadro = reloj()  # instante del ultimo cuadro recibido (o de la apertura)
        self._espera = espera_inicial_s
        self._proximo_intento = 0.0

    def sin_senal_s(self) -> float:
        """Segundos transcurridos desde el ultimo cuadro recibido."""
        return self.reloj() - self.ultimo_cuadro

    def leer(self):
        ahora = self.reloj()
        if self.captura is None:
            if ahora < self._proximo_intento:
                return False, None
            self._reabrir(ahora)
            if self.captura is None:
                return False, None
        ok, cuadro = self.captura.read()
        if ok:
            self.ultimo_cuadro = ahora
            self._espera = self.espera_inicial_s
            return True, cuadro
        log.warning("La camara dejo de entregar cuadros: se reintenta en %.0f s", self._espera)
        self.liberar()
        self._agendar(ahora)
        return False, None

    def liberar(self) -> None:
        if self.captura is not None:
            self.captura.release()
            self.captura = None

    def _reabrir(self, ahora: float) -> None:
        nueva = self.abrir()
        if nueva.isOpened():
            self.captura = nueva
            self.reconexiones += 1
            log.info("Camara reconectada (reconexion %d)", self.reconexiones)
        else:
            nueva.release()
            log.warning("No se pudo reconectar la camara: se reintenta en %.0f s", self._espera)
            self._agendar(ahora)

    def _agendar(self, ahora: float) -> None:
        self._proximo_intento = ahora + self._espera
        self._espera = min(self.espera_max_s, self._espera * 2)
