import enum

from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class EstadoEquipo(str, enum.Enum):
    operativo = "operativo"
    en_mantenimiento = "en_mantenimiento"
    fuera_de_servicio = "fuera_de_servicio"


class Equipo(Base):
    """Representa una maquina/activo del gimnasio (ej. cinta de correr, banco de pesas)."""

    __tablename__ = "equipos"

    id = Column(Integer, primary_key=True, index=True)
    codigo_qr = Column(String(64), unique=True, index=True, nullable=False)
    nombre = Column(String(120), nullable=False)
    marca = Column(String(80), nullable=True)
    modelo = Column(String(80), nullable=True)
    ubicacion = Column(String(120), nullable=True)
    estado = Column(Enum(EstadoEquipo), default=EstadoEquipo.operativo, nullable=False)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())

    incidencias = relationship(
        "Incidencia", back_populates="equipo", cascade="all, delete-orphan"
    )
