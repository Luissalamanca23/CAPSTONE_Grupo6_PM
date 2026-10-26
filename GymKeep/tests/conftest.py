import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.gymkeep import Empresa, PrioridadIncidencia, Sucursal, TipoFalla, Zona

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"


# Los modelos usan BigInteger como clave primaria (BIGSERIAL en Postgres), pero SQLite solo
# autoincrementa columnas "INTEGER PRIMARY KEY": sin esto, todo INSERT falla con
# "NOT NULL constraint failed: <tabla>.id".
@compiles(BigInteger, "sqlite")
def _bigint_como_integer_en_sqlite(tipo, compilador, **kw):
    return "INTEGER"


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


class _ColeccionFalsa:
    """Coleccion Mongo en memoria con lo minimo que usa services/fotos_incidencias."""

    def __init__(self):
        self.docs = {}

    def replace_one(self, filtro, doc, upsert=False):
        self.docs[filtro["_id"]] = doc

    def find_one(self, filtro, proyeccion=None):
        return self.docs.get(filtro["_id"])

    def find(self, filtro, proyeccion=None):
        ids = filtro["_id"]["$in"]
        return [{"_id": i} for i in ids if i in self.docs]

    def delete_many(self, filtro):
        for i in filtro["_id"]["$in"]:
            self.docs.pop(i, None)


class MongoFotosFalso:
    def __init__(self):
        self.fotos_incidencias = _ColeccionFalsa()


@pytest.fixture(autouse=True)
def mongo_fotos_incidencias(monkeypatch):
    """Las fotos de incidencias van a Mongo; en los tests se usa un Mongo falso en memoria
    (si no, cada listado intentaria conectarse y esperaria el timeout)."""
    from app.services import fotos_incidencias

    falso = MongoFotosFalso()
    monkeypatch.setattr(fotos_incidencias, "get_mongo_db", lambda: falso)
    return falso


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
