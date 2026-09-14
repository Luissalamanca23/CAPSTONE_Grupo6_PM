"""Utilidad de desarrollo para crear las tablas en la base de datos configurada.

Uso: python -m app.init_db

IMPORTANTE (esquema ampliado): en Docker, PostgreSQL crea el esquema real ejecutando
postgres/schema.sql (que ademas define triggers, vistas y datos de ejemplo) la primera
vez que se levanta el volumen, via docker-entrypoint-initdb.d. Este script con
create_all() es solo un respaldo para desarrollo local sin Docker (o para las pruebas con
SQLite en memoria, ver tests/conftest.py): crea las tablas a partir de los modelos de
SQLAlchemy, pero NO crea los triggers ni las vistas (vw_estado_equipos, vw_uso_diario_equipos)
ni el catalogo semilla de tipos_falla. Si usas Docker con docker-compose.yml, no necesitas
ejecutar este script.
"""
import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.core.database import Base, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas correctamente.")


if __name__ == "__main__":
    init_db()
