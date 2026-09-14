import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.gymkeep import Empresa, PrioridadIncidencia, Sucursal, TipoFalla, Zona

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Mismo catalogo semilla que postgres/schema.sql (ver GymKeep_BDD_Completa), para que los
# tests no dependan de una base PostgreSQL real.
CATALOGO_TIPOS_FALLA = [
    dict(
        codigo="DESGASTE",
        nombre="Desgaste visible",
        descripcion="Desgaste visible de piezas o componentes.",
        prioridad_base=PrioridadIncidencia.baja,
        permite_reporte_qr=True,
        permite_deteccion_ia=True,
    ),
    dict(
        codigo="SONIDO_EXTRANO",
        nombre="Sonido extraño",
        descripcion="Ruido o vibración no habitual durante el uso.",
        prioridad_base=PrioridadIncidencia.media,
        permite_reporte_qr=True,
        permite_deteccion_ia=True,
    ),
    dict(
        codigo="ROTA",
        nombre="Pieza rota / no funciona",
        descripcion="Equipo con daño físico o incapaz de operar correctamente.",
        prioridad_base=PrioridadIncidencia.urgente,
        permite_reporte_qr=True,
        permite_deteccion_ia=True,
    ),
    dict(
        codigo="NO_ENCIENDE",
        nombre="No enciende",
        descripcion="Equipo eléctrico/electrónico no inicia.",
        prioridad_base=PrioridadIncidencia.urgente,
        permite_reporte_qr=True,
        permite_deteccion_ia=True,
    ),
    dict(
        codigo="MOVIMIENTO_ANOMALO",
        nombre="Movimiento anómalo",
        descripcion="La IA detecta un patrón mecánico o de uso anómalo.",
        prioridad_base=PrioridadIncidencia.alta,
        permite_reporte_qr=False,
        permite_deteccion_ia=True,
    ),
    dict(
        codigo="OTRO",
        nombre="Otro",
        descripcion="Falla no clasificada.",
        prioridad_base=PrioridadIncidencia.media,
        permite_reporte_qr=True,
        permite_deteccion_ia=False,
    ),
]


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        for datos in CATALOGO_TIPOS_FALLA:
            session.add(TipoFalla(**datos))

        # Empresa/sucursal/zona de demostracion (equivalente a postgres/seed.sql), para que
        # los tests de equipamiento tengan donde registrar equipos.
        empresa = Empresa(razon_social="GymKeep Demo SpA", nombre_fantasia="GymKeep Demo")
        session.add(empresa)
        session.flush()

        sucursal = Sucursal(empresa_id=empresa.id, codigo="PM-01", nombre="Sucursal Puerto Montt")
        session.add(sucursal)
        session.flush()

        zona = Zona(sucursal_id=sucursal.id, nombre="Cardio")
        session.add(zona)
        session.commit()

        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def sucursal_id(db_session):
    return db_session.query(Sucursal).filter(Sucursal.codigo == "PM-01").first().id


@pytest.fixture()
def zona_id(db_session):
    return db_session.query(Zona).filter(Zona.nombre == "Cardio").first().id
