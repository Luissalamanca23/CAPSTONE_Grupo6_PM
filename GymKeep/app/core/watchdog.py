"""Tarea periodica que cierra las sesiones de uso huerfanas (ver ai_event_service).

Si el pipeline se cae en mitad de una sesion nunca envia `fin_uso`; sin esto la sesion
quedaria `abierta` hasta el proximo `inicio_uso` de esa maquina. VISION_WATCHDOG_S define cada
cuantos segundos se revisa (0 la desactiva). La primera revision ocurre pasado un intervalo.
"""

import asyncio
import logging

from app.core import database
from app.core.config import settings
from app.services import ai_event_service

log = logging.getLogger(__name__)


def revisar_una_vez() -> int:
    """Una pasada del watchdog con su propia sesion de base de datos."""
    db = database.SessionLocal()
    try:
        return ai_event_service.cerrar_sesiones_huerfanas(db)
    except Exception:  # la tarea no debe morir por un fallo puntual de la base de datos
        db.rollback()
        log.exception("Watchdog de sesiones de uso: fallo la revision")
        return 0
    finally:
        db.close()


async def bucle(intervalo_s: float) -> None:
    while True:
        await asyncio.sleep(intervalo_s)
        await asyncio.to_thread(revisar_una_vez)


def iniciar() -> "asyncio.Task | None":
    """Lanza la tarea en el loop actual (None si esta desactivada)."""
    if settings.vision_watchdog_s <= 0:
        return None
    return asyncio.create_task(bucle(settings.vision_watchdog_s))
