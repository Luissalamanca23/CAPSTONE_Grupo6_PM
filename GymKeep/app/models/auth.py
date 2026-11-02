"""Usuarios del panel (inicio de sesion con RUN + clave numerica) y configuracion interna.

En Docker las tablas se crean con postgres/schema.sql la primera vez; en bases que ya existian
(volumenes anteriores) la API las crea al arrancar (app/core/arranque.py). Tipos genericos para
que tambien funcionen en SQLite (tests).
"""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, Integer, String, Text, func

from app.core.database import Base

ROL_ADMIN = "admin"
ROL_TECNICO = "tecnico"
ROLES = (ROL_ADMIN, ROL_TECNICO)


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("rol IN ('admin', 'tecnico')", name="ck_usuarios_rol"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # RUN canonico: cuerpo sin puntos, guion y digito verificador (ej. 12345678-5).
    run = Column(String(12), nullable=False, unique=True)
    nombre = Column(String(120), nullable=False)
    rol = Column(String(20), nullable=False, default=ROL_TECNICO, server_default=ROL_TECNICO)
    clave_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, nullable=False, default=True, server_default="true")
    intentos_fallidos = Column(Integer, nullable=False, default=0, server_default="0")
    bloqueado_hasta = Column(DateTime(timezone=True))
    # Se incrementa al cambiar la clave o desactivar la cuenta: invalida las sesiones abiertas.
    sesion_version = Column(Integer, nullable=False, default=0, server_default="0")
    ultimo_acceso = Column(DateTime(timezone=True))
    creado_en = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @property
    def es_admin(self) -> bool:
        return self.rol == ROL_ADMIN


class ConfigAuth(Base):
    """Pares clave/valor internos (hoy: el secreto con que se firman las sesiones)."""

    __tablename__ = "auth_config"

    clave = Column(String(50), primary_key=True)
    valor = Column(Text, nullable=False)
