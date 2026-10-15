"""Registro de presencia (`presencia.csv`) que no crece sin tope en modo 24/7.

Con un archivo de video se escribe un solo CSV, como siempre. Con `rotar=True` (camara en
vivo) el archivo se cierra y se archiva cuando cambia el dia o supera `max_bytes`, y se
conservan solo los ultimos `max_archivos`. `recalibrar` lee el archivo vigente o cualquiera
de los archivados (mismo formato, misma cabecera).
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

CABECERA = ["t_s", "timestamp", "maquina", "personas", "confianza_max", "estado"]


class RegistroPresencia:
    def __init__(self, ruta: Path, *, rotar: bool = False, max_bytes: int = 50_000_000, max_archivos: int = 7):
        self.ruta = ruta
        self.rotar = rotar
        self.max_bytes = max_bytes
        self.max_archivos = max_archivos
        self._dia: str | None = None
        self._bytes = 0
        if rotar and ruta.exists() and ruta.stat().st_size > 0:
            # Reinicio del proceso: lo de la corrida anterior se archiva en vez de borrarse.
            self._archivar(datetime.fromtimestamp(ruta.stat().st_mtime).strftime("%Y-%m-%d"))
        self._abrir()

    def escribir(self, fila: list) -> None:
        dia = str(fila[1])[:10]  # el timestamp es ISO 8601: los 10 primeros caracteres son la fecha
        if self.rotar and self._dia is not None and (dia != self._dia or self._bytes >= self.max_bytes):
            self._cerrar_archivo()
            self._archivar(self._dia)
            self._abrir()
        self._dia = dia
        self._csv.writerow(fila)
        self._bytes += sum(len(str(c)) + 1 for c in fila) + 1
        if self.rotar:
            self._archivo.flush()

    def cerrar(self) -> None:
        self._cerrar_archivo()

    def _abrir(self) -> None:
        self._archivo = self.ruta.open("w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._archivo)
        self._csv.writerow(CABECERA)
        self._bytes = sum(len(c) + 1 for c in CABECERA) + 1

    def _cerrar_archivo(self) -> None:
        if not self._archivo.closed:
            self._archivo.close()

    def _archivar(self, dia: str) -> None:
        n = 1
        while (destino := self.ruta.with_name(f"{self.ruta.stem}.{dia}.{n}{self.ruta.suffix}")).exists():
            n += 1
        self.ruta.replace(destino)
        archivados = sorted(
            self.ruta.parent.glob(f"{self.ruta.stem}.*{self.ruta.suffix}"), key=lambda r: r.stat().st_mtime
        )
        for viejo in archivados[: max(0, len(archivados) - self.max_archivos)]:
            viejo.unlink()
            log.info("Presencia archivada eliminada por antiguedad: %s", viejo.name)
