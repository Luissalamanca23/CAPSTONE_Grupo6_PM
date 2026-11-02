"""Limitador simple en memoria (ventana deslizante)."""

import threading
import time
from collections import defaultdict, deque


class LimitadorVentana:
    """Permite `maximo` eventos por `ventana` segundos para cada clave. Es por proceso: sirve
    contra abuso casual de los endpoints publicos; si la API corre en varios procesos, cada uno
    cuenta aparte."""

    def __init__(self, maximo: int, ventana: float):
        self.maximo = maximo
        self.ventana = ventana
        self._eventos: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def permitir(self, clave) -> bool:
        ahora = time.monotonic()
        with self._lock:
            cola = self._eventos[clave]
            while cola and ahora - cola[0] > self.ventana:
                cola.popleft()
            if len(cola) >= self.maximo:
                return False
            cola.append(ahora)
            return True

    def reiniciar(self) -> None:
        with self._lock:
            self._eventos.clear()
