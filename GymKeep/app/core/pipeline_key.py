"""Clave del pipeline de vision.

Los endpoints que solo usa el pipeline (configuracion de la camara, estado en vivo, eventos de
IA) piden la cabecera X-Pipeline-Key cuando VISION_PIPELINE_KEY esta configurada. Sin clave
configurada quedan abiertos (desarrollo). Es una clave compartida entre la API y el pipeline,
distinta del PIN de edicion del panel (app/core/pin.py).
"""

import hmac
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings
from app.core.pin import pin_requerido, verificar_pin


def clave_requerida() -> bool:
    return bool(settings.vision_pipeline_key)


def _clave_valida(x_pipeline_key: Optional[str]) -> bool:
    return x_pipeline_key is not None and hmac.compare_digest(
        x_pipeline_key.encode(), settings.vision_pipeline_key.encode()
    )


def verificar_clave_pipeline(x_pipeline_key: Optional[str] = Header(default=None)) -> None:
    """Dependencia de FastAPI para los endpoints del pipeline."""
    if not clave_requerida():
        return
    if not _clave_valida(x_pipeline_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Clave del pipeline invalida.")


def verificar_clave_o_pin(
    request: Request,
    x_pipeline_key: Optional[str] = Header(default=None),
    x_vision_pin: Optional[str] = Header(default=None),
) -> None:
    """Para el cuadro de la camara: lo sube el pipeline (clave) o el panel (PIN de edicion)."""
    if clave_requerida() and _clave_valida(x_pipeline_key):
        return
    if pin_requerido():
        verificar_pin(request, x_vision_pin)
        return
    if clave_requerida():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Se requiere la clave del pipeline o el PIN.")
