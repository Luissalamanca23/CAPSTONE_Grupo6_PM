import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class EstadoIncidencia(str, enum.Enum):
    pendiente = "pendiente"
    en_proceso = "en_proceso"
    resuelta = "resuelta"
    descartada = "descartada"


class PrioridadIncidencia(str, enum.Enum):
    baja = "baja"
    media = "media"
    alta = "alta"
    urgente = "urgente"


class TipoFalla(str, enum.Enum):
    """Categorias fijas que el cliente elige en la encuesta del Portal de Reporte Express
    (sin texto libre, salvo su nombre)."""

    desgaste = "desgaste"
    sonido_extrano = "sonido_extrano"
    rota = "rota"
    no_enciende = "no_enciende"
    otro = "otro"


# Etiqueta corta para mostrar en botones/tarjetas de seleccion y en tablas del panel.
ETIQUETA_TIPO_FALLA = {
    TipoFalla.desgaste: "Desgaste",
    TipoFalla.sonido_extrano: "Sonido extraño",
    TipoFalla.rota: "Rota / no funciona",
    TipoFalla.no_enciende: "No enciende",
    TipoFalla.otro: "Otro",
}

# Descripcion completa auto-generada cuando el reporte viene del formulario publico
# (el cliente no escribe texto, solo elige una opcion).
DESCRIPCION_TIPO_FALLA = {
    TipoFalla.desgaste: "El equipo presenta desgaste visible en sus componentes.",
    TipoFalla.sonido_extrano: "El equipo hace un sonido extraño durante su uso.",
    TipoFalla.rota: "El equipo tiene una pieza rota o no funciona.",
    TipoFalla.no_enciende: "El equipo no enciende.",
    TipoFalla.otro: "Se reporto una falla de otro tipo.",
}

# Clasificacion automatica de urgencia segun el tipo de falla reportado.
NIVEL_POR_TIPO_FALLA = {
    TipoFalla.rota: PrioridadIncidencia.urgente,
    TipoFalla.no_enciende: PrioridadIncidencia.urgente,
    TipoFalla.sonido_extrano: PrioridadIncidencia.media,
    TipoFalla.desgaste: PrioridadIncidencia.baja,
    TipoFalla.otro: PrioridadIncidencia.media,
}


class Incidencia(Base):
    """Reporte de falla de un equipo, generado por un socio o personal tras escanear el QR.

    Se guarda fecha_reporte automaticamente (dia y hora) para poder ordenar y clasificar
    los incidentes de cada maquina en el tiempo."""

    __tablename__ = "incidencias"

    id = Column(Integer, primary_key=True, index=True)
    equipo_id = Column(Integer, ForeignKey("equipos.id", ondelete="CASCADE"), nullable=False)
    tipo_falla = Column(Enum(TipoFalla), nullable=False)
    # Se autocompleta a partir de tipo_falla si no se especifica (el formulario publico
    # no pide texto libre, salvo el nombre de quien reporta).
    descripcion = Column(Text, nullable=True)
    reportado_por = Column(String(120), nullable=True)
    estado = Column(Enum(EstadoIncidencia), default=EstadoIncidencia.pendiente, nullable=False)
    prioridad = Column(Enum(PrioridadIncidencia), default=PrioridadIncidencia.media, nullable=False)
    fecha_reporte = Column(DateTime(timezone=True), server_default=func.now())
    fecha_resolucion = Column(DateTime(timezone=True), nullable=True)

    equipo = relationship("Equipo", back_populates="incidencias")
