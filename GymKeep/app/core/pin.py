"""PIN de edicion del modulo de vision.

Proteccion liviana (no es un sistema de usuarios): editar las zonas de las maquinas y los
parametros de deteccion pide un PIN numerico de 4 a 6 digitos, configurado en VISION_PIN. El
panel lo envia en la cabecera X-Vision-Pin. Sin VISION_PIN la edicion queda libre (desarrollo).

Para que no se pueda adivinar probando, tras INTENTOS_MAX fallos seguidos desde la misma IP
se bloquea esa IP durante BLOQUEO_S segundos.
"""

import hmac
import logging
import time
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings

log = logging.getLogger(__name__)

INTENTOS_MAX = 5
BLOQUEO_S = 60

_fallos: dict[str, tuple[int, float]] = {}  # ip -> (fallos seguidos, bloqueada hasta)


def pin_requerido() -> bool:
    return bool(settings.vision_pin)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


def verificar_pin(request: Request, x_vision_pin: Optional[str] = Header(default=None)) -> None:
    """Dependencia de FastAPI para los endpoints que modifican la configuracion de vision."""
    if not pin_requerido():
        return
    ip, ahora = _ip(request), time.monotonic()
    fallos, hasta = _fallos.get(ip, (0, 0.0))
    if hasta > ahora:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos. Espera {int(hasta - ahora) + 1} s.",
        )
    if x_vision_pin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere el PIN de edicion.")
    if hmac.compare_digest(x_vision_pin.encode(), settings.vision_pin.encode()):
        _fallos.pop(ip, None)
        return
    fallos += 1
    if fallos >= INTENTOS_MAX:
        log.warning("PIN de vision: %s bloqueada %s s tras %s intentos fallidos", ip, BLOQUEO_S, fallos)
        _fallos[ip] = (0, ahora + BLOQUEO_S)
    else:
        _fallos[ip] = (fallos, 0.0)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PIN incorrecto.")


def reiniciar_intentos() -> None:
    """Para los tests."""
    _fallos.clear()
