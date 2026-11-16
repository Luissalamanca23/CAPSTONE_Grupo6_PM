import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# La API no debe tocar la base real al arrancar (crear tablas) durante los tests.
os.environ["SKIP_DB_INIT"] = "1"

from app.core import auth  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.crud import usuario as crud_usuario  # noqa: E402
from app.main import app  # noqa: E402
from app.models.gymkeep import Empresa, PrioridadIncidencia, Sucursal, TipoFalla, Zona

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

# Cuentas de prueba (RUN con digito verificador valido).
RUN_ADMIN, CLAVE_ADMIN = "12345678-5", "1234"
RUN_TECNICO, CLAVE_TECNICO = "22222222-2", "4321"


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

# Mismo catalogo semilla que postgres/schema.sql, para que los
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


@pytest.fixture(autouse=True)
def reiniciar_estado_de_login():
    """El secreto de sesion y los contadores de intentos viven en memoria del proceso."""
    from app.api.v1 import auth as auth_api

    auth.reiniciar_cache_secreto()
    auth_api.limitador_login_ip.reiniciar()
    yield
    auth.reiniciar_cache_secreto()


@pytest.fixture()
def client_anonimo(db_session):
    """Cliente sin sesion iniciada (como alguien que abre el panel o la API sin entrar)."""

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
def admin(db_session):
    return crud_usuario.crear(db_session, RUN_ADMIN, "Admin de Prueba", "admin", CLAVE_ADMIN)


@pytest.fixture()
def tecnico(db_session):
    return crud_usuario.crear(db_session, RUN_TECNICO, "Tecnico de Prueba", "tecnico", CLAVE_TECNICO)


def iniciar_sesion(cliente, run, clave):
    respuesta = cliente.post("/api/v1/auth/login", json={"run": run, "clave": clave})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta


@pytest.fixture()
def client(client_anonimo, admin):
    """Cliente con la sesion de un administrador: asi los tests de cada modulo ejercen la API
    como lo hace el panel. Los controles de acceso se prueban en tests/test_auth.py."""
    iniciar_sesion(client_anonimo, RUN_ADMIN, CLAVE_ADMIN)
    return client_anonimo


@pytest.fixture()
def client_tecnico(client_anonimo, tecnico):
    iniciar_sesion(client_anonimo, RUN_TECNICO, CLAVE_TECNICO)
    return client_anonimo


@pytest.fixture()
def sucursal_id(db_session):
    return db_session.query(Sucursal).filter(Sucursal.codigo == "PM-01").first().id


@pytest.fixture()
def zona_id(db_session):
    return db_session.query(Zona).filter(Zona.nombre == "Cardio").first().id
