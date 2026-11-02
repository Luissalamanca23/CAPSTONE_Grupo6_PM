"""Origenes de confianza del panel (CORS y proteccion contra peticiones de otros sitios).

El panel y la API normalmente comparten dominio (nginx de la demo o el proxy de Vite), pero en
desarrollo el panel esta en :5173 y la API en :8000. Se aceptan localhost, redes privadas y la
red de Tailscale, el FRONTEND_URL y los de CORS_ORIGINS (separados por comas).
"""

import re
from typing import Optional
from urllib.parse import urlsplit

from app.core.config import settings

# localhost, 127.x, 10.x, 172.16-31.x, 192.168.x y 100.64-127.x (Tailscale), con o sin puerto.
ORIGEN_LOCAL_RE = (
    r"^https?://(localhost|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+"
    r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)(:\d+)?$"
)


def origenes_permitidos() -> list[str]:
    lista = []
    for valor in [settings.frontend_url, *settings.cors_origins.split(",")]:
        valor = valor.strip().rstrip("/")
        if valor:
            lista.append(valor)
    return lista


def _host(url: Optional[str]) -> Optional[str]:
    return urlsplit(url).hostname if url else None


def origen_confiable(origen: str, host_peticion: Optional[str], host_reenviado: Optional[str] = None) -> bool:
    """True si el Origin de una peticion que modifica datos es del mismo sitio o de confianza."""
    if re.match(ORIGEN_LOCAL_RE, origen) or origen.rstrip("/") in origenes_permitidos():
        return True
    hostname = _host(origen)
    if not hostname:
        return False
    propios = {_host(f"//{host_peticion}") if host_peticion else None, _host(f"//{host_reenviado}") if host_reenviado else None}
    return hostname in {h for h in propios if h}
