"""Tareas de arranque de la API."""

import logging

from app.core.config import settings
from app.core.database import Base, engine
from app.models.auth import ConfigAuth, Usuario

log = logging.getLogger("gymkeep.arranque")


def asegurar_tablas() -> None:
    """Crea las tablas del login si faltan.

    La base ya existente (volumen de Postgres creado antes del login) no ejecuta de nuevo
    postgres/schema.sql, asi que la API crea aqui solo `usuarios` y `auth_config`. No toca el
    resto del esquema. Si la base no responde, el login tampoco funcionara, pero la API arranca.
    """
    if settings.skip_db_init:
        return
    try:
        Base.metadata.create_all(bind=engine, tables=[Usuario.__table__, ConfigAuth.__table__])
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudieron verificar las tablas de usuarios: %s", exc)
