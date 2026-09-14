"""
Modelos SQLAlchemy centrales de GymKeep.

Para una integración progresiva, este archivo puede utilizarse como referencia o
separarse posteriormente en empresa.py, sucursal.py, equipo.py, incidencia.py, etc.
"""

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EstadoEmpresa(str, enum.Enum):
    activa = "activa"
    inactiva = "inactiva"


class EstadoSucursal(str, enum.Enum):
    activa = "activa"
    inactiva = "inactiva"
    mantenimiento = "mantenimiento"


class EstadoEquipo(str, enum.Enum):
    operativo = "operativo"
    en_mantenimiento = "en_mantenimiento"
    fuera_de_servicio = "fuera_de_servicio"
    retirado = "retirado"


class EstadoCamara(str, enum.Enum):
    activa = "activa"
    inactiva = "inactiva"
    error = "error"
    mantenimiento = "mantenimiento"


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


class OrigenIncidencia(str, enum.Enum):
    qr = "qr"
    ia = "ia"
    tecnico = "tecnico"
    sistema = "sistema"


class OrigenUso(str, enum.Enum):
    ia = "ia"
    manual = "manual"
    sensor = "sensor"


class TipoEventoIA(str, enum.Enum):
    persona_detectada = "persona_detectada"
    inicio_uso = "inicio_uso"
    fin_uso = "fin_uso"
    uso_en_curso = "uso_en_curso"
    anomalia = "anomalia"
    posible_falla = "posible_falla"
    ocupacion_zona = "ocupacion_zona"


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(BigInteger, primary_key=True)
    rut = Column(String(20), unique=True, nullable=True)
    razon_social = Column(String(180), nullable=False)
    nombre_fantasia = Column(String(180))
    email_contacto = Column(String(180))
    telefono = Column(String(40))
    estado = Column(Enum(EstadoEmpresa, name="estado_empresa"), nullable=False, default=EstadoEmpresa.activa)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sucursales = relationship("Sucursal", back_populates="empresa", cascade="all, delete-orphan")


class Sucursal(Base):
    __tablename__ = "sucursales"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="uq_sucursal_empresa_codigo"),)

    id = Column(BigInteger, primary_key=True)
    empresa_id = Column(BigInteger, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(50), nullable=False)
    nombre = Column(String(180), nullable=False)
    direccion = Column(String(250))
    comuna = Column(String(120))
    ciudad = Column(String(120))
    region = Column(String(120))
    pais = Column(String(80), nullable=False, default="Chile")
    latitud = Column(Numeric(10, 7))
    longitud = Column(Numeric(10, 7))
    zona_horaria = Column(String(60), nullable=False, default="America/Santiago")
    estado = Column(Enum(EstadoSucursal, name="estado_sucursal"), nullable=False, default=EstadoSucursal.activa)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    empresa = relationship("Empresa", back_populates="sucursales")
    zonas = relationship("Zona", back_populates="sucursal", cascade="all, delete-orphan")
    equipos = relationship("Equipo", back_populates="sucursal")
    camaras = relationship("Camara", back_populates="sucursal")


class Zona(Base):
    __tablename__ = "zonas"
    __table_args__ = (UniqueConstraint("sucursal_id", "nombre", name="uq_zona_sucursal_nombre"),)

    id = Column(BigInteger, primary_key=True)
    sucursal_id = Column(BigInteger, ForeignKey("sucursales.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String(120), nullable=False)
    descripcion = Column(String(250))
    piso = Column(String(30))
    activa = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sucursal = relationship("Sucursal", back_populates="zonas")
    equipos = relationship("Equipo", back_populates="zona")
    camaras = relationship("Camara", back_populates="zona")


camara_equipos = Table(
    "camara_equipos",
    Base.metadata,
    Column("camara_id", BigInteger, ForeignKey("camaras.id", ondelete="CASCADE"), primary_key=True),
    Column("equipo_id", BigInteger, ForeignKey("equipos.id", ondelete="CASCADE"), primary_key=True),
    Column("roi", JSONB),
    Column("activo", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (
        UniqueConstraint("sucursal_id", "codigo_activo", name="uq_equipo_sucursal_codigo"),
        CheckConstraint("vida_util_meses IS NULL OR vida_util_meses > 0", name="ck_equipo_vida_util"),
    )

    id = Column(BigInteger, primary_key=True)
    sucursal_id = Column(BigInteger, ForeignKey("sucursales.id", ondelete="RESTRICT"), nullable=False, index=True)
    zona_id = Column(BigInteger, ForeignKey("zonas.id", ondelete="SET NULL"), index=True)
    codigo_activo = Column(String(64), nullable=False)
    nombre = Column(String(120), nullable=False)
    categoria = Column(String(100))
    marca = Column(String(80))
    modelo = Column(String(80))
    numero_serie = Column(String(120), unique=True)
    fecha_adquisicion = Column(Date)
    fecha_instalacion = Column(Date)
    vida_util_meses = Column(Integer)
    estado = Column(Enum(EstadoEquipo, name="estado_equipo"), nullable=False, default=EstadoEquipo.operativo)
    observaciones = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sucursal = relationship("Sucursal", back_populates="equipos")
    zona = relationship("Zona", back_populates="equipos")
    qr = relationship("QrEquipo", back_populates="equipo", cascade="all, delete-orphan")
    incidencias = relationship("Incidencia", back_populates="equipo")
    mantenimientos = relationship("Mantenimiento", back_populates="equipo")
    sesiones_uso = relationship("SesionUso", back_populates="equipo")
    camaras = relationship("Camara", secondary=camara_equipos, back_populates="equipos")


class QrEquipo(Base):
    __tablename__ = "qr_equipos"

    id = Column(BigInteger, primary_key=True)
    equipo_id = Column(BigInteger, ForeignKey("equipos.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(UUID(as_uuid=True), nullable=False, unique=True, default=uuid.uuid4)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_emision = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_expiracion = Column(DateTime(timezone=True))
    fecha_revocacion = Column(DateTime(timezone=True))
    motivo_revocacion = Column(String(250))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipo = relationship("Equipo", back_populates="qr")


class Camara(Base):
    __tablename__ = "camaras"
    __table_args__ = (UniqueConstraint("sucursal_id", "codigo", name="uq_camara_sucursal_codigo"),)

    id = Column(BigInteger, primary_key=True)
    sucursal_id = Column(BigInteger, ForeignKey("sucursales.id", ondelete="CASCADE"), nullable=False, index=True)
    zona_id = Column(BigInteger, ForeignKey("zonas.id", ondelete="SET NULL"), index=True)
    codigo = Column(String(60), nullable=False)
    nombre = Column(String(120), nullable=False)
    fabricante = Column(String(100))
    modelo = Column(String(100))
    ip = Column(String(64))
    rtsp_url = Column(String(500))
    fps_configurado = Column(Numeric(6, 2))
    ancho_px = Column(Integer)
    alto_px = Column(Integer)
    estado = Column(Enum(EstadoCamara, name="estado_camara"), nullable=False, default=EstadoCamara.activa)
    ultima_conexion = Column(DateTime(timezone=True))
    configuracion = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sucursal = relationship("Sucursal", back_populates="camaras")
    zona = relationship("Zona", back_populates="camaras")
    equipos = relationship("Equipo", secondary=camara_equipos, back_populates="camaras")


class ModeloIA(Base):
    __tablename__ = "modelos_ia"
    __table_args__ = (UniqueConstraint("nombre", "version", name="uq_modelo_ia_nombre_version"),)

    id = Column(BigInteger, primary_key=True)
    nombre = Column(String(120), nullable=False)
    version = Column(String(60), nullable=False)
    framework = Column(String(80))
    tipo_modelo = Column(String(80))
    clases = Column(JSONB, nullable=False, default=list)
    metricas = Column(JSONB, nullable=False, default=dict)
    checksum = Column(String(128))
    ruta_artefacto = Column(String(500))
    activo = Column(Boolean, nullable=False, default=True)
    fecha_despliegue = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TipoFalla(Base):
    __tablename__ = "tipos_falla"

    id = Column(BigInteger, primary_key=True)
    codigo = Column(String(50), nullable=False, unique=True)
    nombre = Column(String(120), nullable=False)
    descripcion = Column(Text)
    prioridad_base = Column(
        Enum(PrioridadIncidencia, name="prioridad_incidencia"),
        nullable=False,
        default=PrioridadIncidencia.media,
    )
    permite_reporte_qr = Column(Boolean, nullable=False, default=True)
    permite_deteccion_ia = Column(Boolean, nullable=False, default=False)
    activa = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Incidencia(Base):
    __tablename__ = "incidencias"

    id = Column(BigInteger, primary_key=True)
    equipo_id = Column(BigInteger, ForeignKey("equipos.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo_falla_id = Column(BigInteger, ForeignKey("tipos_falla.id", ondelete="RESTRICT"), nullable=False)
    qr_id = Column(BigInteger, ForeignKey("qr_equipos.id", ondelete="SET NULL"))
    camara_id = Column(BigInteger, ForeignKey("camaras.id", ondelete="SET NULL"))
    modelo_ia_id = Column(BigInteger, ForeignKey("modelos_ia.id", ondelete="SET NULL"))
    evento_ia_uuid = Column(UUID(as_uuid=True), index=True)
    origen = Column(Enum(OrigenIncidencia, name="origen_incidencia"), nullable=False)
    descripcion = Column(Text)
    reportado_por = Column(String(120))
    prioridad = Column(
        Enum(PrioridadIncidencia, name="prioridad_incidencia"),
        nullable=False,
        default=PrioridadIncidencia.media,
    )
    estado = Column(
        Enum(EstadoIncidencia, name="estado_incidencia"),
        nullable=False,
        default=EstadoIncidencia.pendiente,
    )
    fecha_reporte = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_resolucion = Column(DateTime(timezone=True))
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipo = relationship("Equipo", back_populates="incidencias")
    tipo_falla = relationship("TipoFalla")
    camara = relationship("Camara")
    modelo_ia = relationship("ModeloIA")


class Mantenimiento(Base):
    __tablename__ = "mantenimientos"

    id = Column(BigInteger, primary_key=True)
    equipo_id = Column(BigInteger, ForeignKey("equipos.id", ondelete="RESTRICT"), nullable=False, index=True)
    incidencia_id = Column(BigInteger, ForeignKey("incidencias.id", ondelete="SET NULL"), index=True)
    tipo = Column(String(60), nullable=False)
    tecnico = Column(String(150))
    proveedor = Column(String(180))
    descripcion = Column(Text, nullable=False)
    repuestos = Column(JSONB, nullable=False, default=list)
    costo_total = Column(Numeric(14, 2))
    fecha_inicio = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_fin = Column(DateTime(timezone=True))
    proximo_mantenimiento = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipo = relationship("Equipo", back_populates="mantenimientos")
    incidencia = relationship("Incidencia")


class SesionUso(Base):
    __tablename__ = "sesiones_uso"

    id = Column(BigInteger, primary_key=True)
    equipo_id = Column(BigInteger, ForeignKey("equipos.id", ondelete="RESTRICT"), nullable=False, index=True)
    camara_id = Column(BigInteger, ForeignKey("camaras.id", ondelete="SET NULL"), index=True)
    modelo_ia_id = Column(BigInteger, ForeignKey("modelos_ia.id", ondelete="SET NULL"))
    origen = Column(Enum(OrigenUso, name="origen_uso"), nullable=False, default=OrigenUso.ia)
    fecha_inicio = Column(DateTime(timezone=True), nullable=False)
    fecha_fin = Column(DateTime(timezone=True))
    duracion_segundos = Column(Integer)
    confianza_promedio = Column(Numeric(5, 4))
    cantidad_eventos = Column(Integer, nullable=False, default=0)
    evento_inicio_uuid = Column(UUID(as_uuid=True))
    evento_fin_uuid = Column(UUID(as_uuid=True))
    estado = Column(String(30), nullable=False, default="abierta")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipo = relationship("Equipo", back_populates="sesiones_uso")
    camara = relationship("Camara")
    modelo_ia = relationship("ModeloIA")


class EventoIAResumen(Base):
    __tablename__ = "eventos_ia_resumen"

    id = Column(BigInteger, primary_key=True)
    evento_uuid = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    equipo_id = Column(BigInteger, ForeignKey("equipos.id", ondelete="SET NULL"), index=True)
    camara_id = Column(BigInteger, ForeignKey("camaras.id", ondelete="RESTRICT"), nullable=False, index=True)
    modelo_ia_id = Column(BigInteger, ForeignKey("modelos_ia.id", ondelete="SET NULL"))
    sesion_uso_id = Column(BigInteger, ForeignKey("sesiones_uso.id", ondelete="SET NULL"))
    tipo_evento = Column(Enum(TipoEventoIA, name="tipo_evento_ia"), nullable=False)
    timestamp_evento = Column(DateTime(timezone=True), nullable=False, index=True)
    confidence = Column(Numeric(5, 4))
    mongo_collection = Column(String(80), nullable=False, default="eventos_ia")
    snapshot_url = Column(String(700))
    clip_url = Column(String(700))
    procesado = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RegistroAuditoria(Base):
    __tablename__ = "registros_auditoria"

    id = Column(BigInteger, primary_key=True)
    empresa_id = Column(BigInteger, ForeignKey("empresas.id", ondelete="SET NULL"))
    sucursal_id = Column(BigInteger, ForeignKey("sucursales.id", ondelete="SET NULL"))
    actor = Column(String(160))
    actor_tipo = Column(String(40), nullable=False, default="sistema")
    accion = Column(String(120), nullable=False)
    entidad = Column(String(100), nullable=False)
    entidad_id = Column(String(100))
    datos_anteriores = Column(JSONB)
    datos_nuevos = Column(JSONB)
    ip_origen = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
