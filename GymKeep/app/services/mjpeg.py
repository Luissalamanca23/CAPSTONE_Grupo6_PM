"""Video en vivo de una camara como flujo MJPEG (`multipart/x-mixed-replace`).

El navegador lo muestra en una simple etiqueta <img>: cada parte reemplaza a la anterior, asi
que no hace falta JavaScript ni librerias de video. El pipeline de vision deja el ultimo
cuadro en MongoDB cada ~1 s; aqui se revisa varias veces por segundo y se envia solo cuando
hay uno nuevo.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Awaitable, Callable

from starlette.concurrency import run_in_threadpool

BOUNDARY = "gymkeepframe"
MEDIA_TYPE = f"multipart/x-mixed-replace; boundary={BOUNDARY}"

# (id de camara, marca del ultimo cuadro entregado) -> (marca, jpeg) si hay uno mas nuevo, o None
LectorCuadro = Callable[[int, object], "tuple[object, bytes] | None"]


def parte(jpeg: bytes) -> bytes:
    """Una parte del flujo: cabeceras + JPEG."""
    cabecera = (
        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n"
    ).encode("ascii")
    return cabecera + jpeg + b"\r\n"


async def flujo(
    camara_id: int,
    leer_si_nuevo: LectorCuadro,
    *,
    cada_s: float = 0.25,
    repetir_cada_s: float = 10.0,
    desconectado: Callable[[], Awaitable[bool]] | None = None,
    max_s: float | None = None,
) -> AsyncIterator[bytes]:
    """Genera las partes del flujo hasta que el cliente se desconecta (o pasen `max_s`).

    - Revisa si hay un cuadro nuevo cada `cada_s` (la lectura va a un hilo: pymongo es bloqueante).
    - Si pasan `repetir_cada_s` sin cuadros nuevos reenvia el ultimo, para que proxies y
      navegadores no den por muerta la conexion.
    """
    ultimo = None
    ultimo_jpeg: bytes | None = None
    transcurrido = 0.0
    sin_novedad = 0.0
    while max_s is None or transcurrido < max_s:
        if desconectado is not None and await desconectado():
            return
        resultado = await run_in_threadpool(leer_si_nuevo, camara_id, ultimo)
        if resultado is not None:
            ultimo, ultimo_jpeg = resultado
            sin_novedad = 0.0
            yield parte(ultimo_jpeg)
        elif ultimo_jpeg is not None and sin_novedad >= repetir_cada_s:
            sin_novedad = 0.0
            yield parte(ultimo_jpeg)
        await asyncio.sleep(cada_s)
        transcurrido += cada_s
        sin_novedad += cada_s
