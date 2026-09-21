from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# pool_pre_ping evita errores por conexiones caidas cuando Postgres se reinicia.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: entrega una sesion de base de datos por request y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
