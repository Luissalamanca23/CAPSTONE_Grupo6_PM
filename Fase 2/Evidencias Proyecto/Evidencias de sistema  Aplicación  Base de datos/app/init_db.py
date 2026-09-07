"""Utilidad de desarrollo para crear las tablas en la base de datos configurada.

Uso: python -m app.init_db

Nota: para un entorno productivo se recomienda usar migraciones versionadas
(Alembic) en lugar de este script.
"""
import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.core.database import Base, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas correctamente.")


if __name__ == "__main__":
    init_db()
