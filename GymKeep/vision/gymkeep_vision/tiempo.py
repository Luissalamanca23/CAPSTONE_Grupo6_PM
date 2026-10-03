"""Reloj del pipeline: a que hora real corresponde cada cuadro y como se muestra.

Todo el pipeline trabaja con `t` = segundos reales desde el primer cuadro. La hora real de
ese primer cuadro (`inicio`) se decide una vez, con esta prioridad:

1. `--inicio` en la linea de comandos (lo correcto para un video grabado).
2. `creation_time` de los metadatos del archivo. Ojo: en un video exportado desde un
   grabador suele ser la hora de exportacion, no la de grabacion.
3. La hora en que se procesa (lo correcto para una camara en vivo).

El origen queda registrado en el resumen de la corrida, para que nunca se confunda una hora
de grabacion con una de procesamiento.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, tzinfo
from pathlib import Path

ORIGEN_ARGUMENTO = "argumento --inicio"
ORIGEN_METADATOS = "metadatos del video (creation_time)"
ORIGEN_AHORA = "hora de procesamiento"


def leer_creation_time(ruta: Path) -> datetime | None:
    """`creation_time` del contenedor (MP4/MOV), si existe y es plausible."""
    if shutil.which("ffprobe") is None or not ruta.exists():
        return None
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time", "-of", "json", str(ruta)],
        capture_output=True, text=True,
    )
    try:
        valor = json.loads(salida.stdout)["format"]["tags"]["creation_time"]
        momento = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
    # Algunos codificadores escriben 1970-01-01 o fechas en blanco: no son una hora real.
    return momento if momento.year >= 2000 else None


def resolver_inicio(
    fuente: str, inicio_arg: str | None, zona: tzinfo, ahora: datetime | None = None
) -> tuple[datetime, str]:
    """Hora real del primer cuadro y de donde salio (ver docstring del modulo)."""
    if inicio_arg:
        inicio = datetime.fromisoformat(inicio_arg)
        return (inicio if inicio.tzinfo else inicio.replace(tzinfo=zona)), ORIGEN_ARGUMENTO
    creacion = leer_creation_time(Path(fuente))
    if creacion is not None:
        return creacion.astimezone(zona), ORIGEN_METADATOS
    return (ahora or datetime.now(zona)), ORIGEN_AHORA


def periodo_salida(fps_archivo: float, salto: int, escala: float) -> float:
    """Segundos reales que representa cada cuadro del video anotado.

    En un archivo se anota 1 de cada `salto` cuadros. Si el grabador exporto el video
    acelerado (`escala` < 1), cada cuadro del archivo dura menos tiempo real: el video
    anotado tiene que reproducirse mas lento para que el reloj impreso avance al ritmo
    del tiempo real."""
    return salto / fps_archivo * escala


def cuadros_pendientes(t: float, t_inicio: float, periodo: float, escritos: int) -> int:
    """Cuantas veces escribir el cuadro actual para que el video anotado no se adelante ni se
    atrase respecto del reloj: en vivo, si el analisis se demora, el cuadro se repite."""
    objetivo = int(round((t - t_inicio) / periodo)) + 1
    return max(0, objetivo - escritos)


def hora(momento: datetime) -> str:
    """Formato para mostrar en pantalla (dd/mm/aaaa hh:mm:ss)."""
    return momento.strftime("%d/%m/%Y %H:%M:%S")


def marca(inicio: datetime, t: float) -> str:
    """Formato para registrar (ISO 8601 con milisegundos y zona horaria)."""
    return (inicio + timedelta(seconds=t)).isoformat(timespec="milliseconds")
