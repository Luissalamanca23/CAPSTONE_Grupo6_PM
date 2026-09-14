-- ============================================================
-- GymKeep - Esquema relacional PostgreSQL
-- Version: 1.0
-- Diseñado para: Empresa -> Sucursal -> Zona -> Equipo
-- + QR + Cámaras + IA + Incidencias + Mantenimiento + Uso
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------- ENUMS ----------
DO $$ BEGIN
    CREATE TYPE estado_empresa AS ENUM ('activa', 'inactiva');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE estado_sucursal AS ENUM ('activa', 'inactiva', 'mantenimiento');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE estado_equipo AS ENUM ('operativo', 'en_mantenimiento', 'fuera_de_servicio', 'retirado');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE estado_camara AS ENUM ('activa', 'inactiva', 'error', 'mantenimiento');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE estado_incidencia AS ENUM ('pendiente', 'en_proceso', 'resuelta', 'descartada');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE prioridad_incidencia AS ENUM ('baja', 'media', 'alta', 'urgente');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE origen_incidencia AS ENUM ('qr', 'ia', 'tecnico', 'sistema');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE origen_uso AS ENUM ('ia', 'manual', 'sensor');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE tipo_evento_ia AS ENUM (
        'persona_detectada',
        'inicio_uso',
        'fin_uso',
        'uso_en_curso',
        'anomalia',
        'posible_falla',
        'ocupacion_zona'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------- FUNCIONES AUXILIARES ----------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_duracion_sesion_uso()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.fecha_fin IS NOT NULL AND NEW.fecha_inicio IS NOT NULL THEN
        NEW.duracion_segundos = GREATEST(
            0,
            FLOOR(EXTRACT(EPOCH FROM (NEW.fecha_fin - NEW.fecha_inicio)))::INTEGER
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_fecha_resolucion_incidencia()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.estado = 'resuelta' AND OLD.estado IS DISTINCT FROM 'resuelta'
       AND NEW.fecha_resolucion IS NULL THEN
        NEW.fecha_resolucion = NOW();
    END IF;

    IF NEW.estado <> 'resuelta' AND OLD.estado = 'resuelta' THEN
        NEW.fecha_resolucion = NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------- EMPRESAS ----------
CREATE TABLE IF NOT EXISTS empresas (
    id BIGSERIAL PRIMARY KEY,
    rut VARCHAR(20),
    razon_social VARCHAR(180) NOT NULL,
    nombre_fantasia VARCHAR(180),
    email_contacto VARCHAR(180),
    telefono VARCHAR(40),
    estado estado_empresa NOT NULL DEFAULT 'activa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_empresas_rut
ON empresas (rut) WHERE rut IS NOT NULL;

-- ---------- SUCURSALES ----------
CREATE TABLE IF NOT EXISTS sucursales (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    codigo VARCHAR(50) NOT NULL,
    nombre VARCHAR(180) NOT NULL,
    direccion VARCHAR(250),
    comuna VARCHAR(120),
    ciudad VARCHAR(120),
    region VARCHAR(120),
    pais VARCHAR(80) NOT NULL DEFAULT 'Chile',
    latitud NUMERIC(10,7),
    longitud NUMERIC(10,7),
    zona_horaria VARCHAR(60) NOT NULL DEFAULT 'America/Santiago',
    estado estado_sucursal NOT NULL DEFAULT 'activa',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sucursal_empresa_codigo UNIQUE (empresa_id, codigo)
);

CREATE INDEX IF NOT EXISTS ix_sucursales_empresa_id ON sucursales(empresa_id);

-- ---------- ZONAS ----------
CREATE TABLE IF NOT EXISTS zonas (
    id BIGSERIAL PRIMARY KEY,
    sucursal_id BIGINT NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(250),
    piso VARCHAR(30),
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_zona_sucursal_nombre UNIQUE (sucursal_id, nombre)
);

CREATE INDEX IF NOT EXISTS ix_zonas_sucursal_id ON zonas(sucursal_id);

-- ---------- EQUIPOS ----------
CREATE TABLE IF NOT EXISTS equipos (
    id BIGSERIAL PRIMARY KEY,
    sucursal_id BIGINT NOT NULL REFERENCES sucursales(id) ON DELETE RESTRICT,
    zona_id BIGINT REFERENCES zonas(id) ON DELETE SET NULL,
    codigo_activo VARCHAR(64) NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    categoria VARCHAR(100),
    marca VARCHAR(80),
    modelo VARCHAR(80),
    numero_serie VARCHAR(120),
    fecha_adquisicion DATE,
    fecha_instalacion DATE,
    vida_util_meses INTEGER CHECK (vida_util_meses IS NULL OR vida_util_meses > 0),
    estado estado_equipo NOT NULL DEFAULT 'operativo',
    observaciones TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_equipo_sucursal_codigo UNIQUE (sucursal_id, codigo_activo)
);

CREATE INDEX IF NOT EXISTS ix_equipos_sucursal_id ON equipos(sucursal_id);
CREATE INDEX IF NOT EXISTS ix_equipos_zona_id ON equipos(zona_id);
CREATE INDEX IF NOT EXISTS ix_equipos_estado ON equipos(estado);
CREATE UNIQUE INDEX IF NOT EXISTS uq_equipos_numero_serie
ON equipos(numero_serie) WHERE numero_serie IS NOT NULL;

-- ---------- QR POR EQUIPO ----------
CREATE TABLE IF NOT EXISTS qr_equipos (
    id BIGSERIAL PRIMARY KEY,
    equipo_id BIGINT NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
    token UUID NOT NULL DEFAULT gen_random_uuid(),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_emision TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_expiracion TIMESTAMPTZ,
    fecha_revocacion TIMESTAMPTZ,
    motivo_revocacion VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_qr_token UNIQUE(token),
    CONSTRAINT ck_qr_fechas CHECK (
        fecha_expiracion IS NULL OR fecha_expiracion > fecha_emision
    )
);

CREATE INDEX IF NOT EXISTS ix_qr_equipos_equipo_id ON qr_equipos(equipo_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_qr_activo_por_equipo
ON qr_equipos(equipo_id) WHERE activo = TRUE;

-- ---------- CAMARAS ----------
CREATE TABLE IF NOT EXISTS camaras (
    id BIGSERIAL PRIMARY KEY,
    sucursal_id BIGINT NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
    zona_id BIGINT REFERENCES zonas(id) ON DELETE SET NULL,
    codigo VARCHAR(60) NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    fabricante VARCHAR(100),
    modelo VARCHAR(100),
    ip VARCHAR(64),
    rtsp_url VARCHAR(500),
    fps_configurado NUMERIC(6,2),
    ancho_px INTEGER,
    alto_px INTEGER,
    estado estado_camara NOT NULL DEFAULT 'activa',
    ultima_conexion TIMESTAMPTZ,
    configuracion JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_camara_sucursal_codigo UNIQUE (sucursal_id, codigo),
    CONSTRAINT ck_camara_fps CHECK (fps_configurado IS NULL OR fps_configurado > 0)
);

CREATE INDEX IF NOT EXISTS ix_camaras_sucursal_id ON camaras(sucursal_id);
CREATE INDEX IF NOT EXISTS ix_camaras_zona_id ON camaras(zona_id);

-- ---------- RELACION CAMARA <-> EQUIPO ----------
-- Una cámara puede observar varios equipos y un equipo puede ser observado por varias cámaras.
CREATE TABLE IF NOT EXISTS camara_equipos (
    camara_id BIGINT NOT NULL REFERENCES camaras(id) ON DELETE CASCADE,
    equipo_id BIGINT NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
    roi JSONB,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (camara_id, equipo_id)
);

CREATE INDEX IF NOT EXISTS ix_camara_equipos_equipo_id ON camara_equipos(equipo_id);

-- ---------- MODELOS DE IA ----------
CREATE TABLE IF NOT EXISTS modelos_ia (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    version VARCHAR(60) NOT NULL,
    framework VARCHAR(80),
    tipo_modelo VARCHAR(80),
    clases JSONB NOT NULL DEFAULT '[]'::jsonb,
    metricas JSONB NOT NULL DEFAULT '{}'::jsonb,
    checksum VARCHAR(128),
    ruta_artefacto VARCHAR(500),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_despliegue TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_modelo_ia_nombre_version UNIQUE(nombre, version)
);

-- ---------- CATALOGO DE FALLAS ----------
CREATE TABLE IF NOT EXISTS tipos_falla (
    id BIGSERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    prioridad_base prioridad_incidencia NOT NULL DEFAULT 'media',
    permite_reporte_qr BOOLEAN NOT NULL DEFAULT TRUE,
    permite_deteccion_ia BOOLEAN NOT NULL DEFAULT FALSE,
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------- INCIDENCIAS ----------
CREATE TABLE IF NOT EXISTS incidencias (
    id BIGSERIAL PRIMARY KEY,
    equipo_id BIGINT NOT NULL REFERENCES equipos(id) ON DELETE RESTRICT,
    tipo_falla_id BIGINT NOT NULL REFERENCES tipos_falla(id) ON DELETE RESTRICT,
    qr_id BIGINT REFERENCES qr_equipos(id) ON DELETE SET NULL,
    camara_id BIGINT REFERENCES camaras(id) ON DELETE SET NULL,
    modelo_ia_id BIGINT REFERENCES modelos_ia(id) ON DELETE SET NULL,
    evento_ia_uuid UUID,
    origen origen_incidencia NOT NULL,
    descripcion TEXT,
    reportado_por VARCHAR(120),
    prioridad prioridad_incidencia NOT NULL DEFAULT 'media',
    estado estado_incidencia NOT NULL DEFAULT 'pendiente',
    fecha_reporte TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_resolucion TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_incidencias_equipo_id ON incidencias(equipo_id);
CREATE INDEX IF NOT EXISTS ix_incidencias_estado ON incidencias(estado);
CREATE INDEX IF NOT EXISTS ix_incidencias_prioridad ON incidencias(prioridad);
CREATE INDEX IF NOT EXISTS ix_incidencias_fecha_reporte ON incidencias(fecha_reporte DESC);
CREATE INDEX IF NOT EXISTS ix_incidencias_evento_ia_uuid ON incidencias(evento_ia_uuid);

-- ---------- MANTENIMIENTOS ----------
CREATE TABLE IF NOT EXISTS mantenimientos (
    id BIGSERIAL PRIMARY KEY,
    equipo_id BIGINT NOT NULL REFERENCES equipos(id) ON DELETE RESTRICT,
    incidencia_id BIGINT REFERENCES incidencias(id) ON DELETE SET NULL,
    tipo VARCHAR(60) NOT NULL CHECK (tipo IN ('preventivo', 'correctivo', 'inspeccion')),
    tecnico VARCHAR(150),
    proveedor VARCHAR(180),
    descripcion TEXT NOT NULL,
    repuestos JSONB NOT NULL DEFAULT '[]'::jsonb,
    costo_total NUMERIC(14,2) CHECK (costo_total IS NULL OR costo_total >= 0),
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_fin TIMESTAMPTZ,
    proximo_mantenimiento DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_mantenimiento_fechas CHECK (
        fecha_fin IS NULL OR fecha_fin >= fecha_inicio
    )
);

CREATE INDEX IF NOT EXISTS ix_mantenimientos_equipo_id ON mantenimientos(equipo_id);
CREATE INDEX IF NOT EXISTS ix_mantenimientos_incidencia_id ON mantenimientos(incidencia_id);

-- ---------- SESIONES DE USO ----------
-- Esta tabla NO guarda cada frame. Guarda un uso consolidado del equipo.
CREATE TABLE IF NOT EXISTS sesiones_uso (
    id BIGSERIAL PRIMARY KEY,
    equipo_id BIGINT NOT NULL REFERENCES equipos(id) ON DELETE RESTRICT,
    camara_id BIGINT REFERENCES camaras(id) ON DELETE SET NULL,
    modelo_ia_id BIGINT REFERENCES modelos_ia(id) ON DELETE SET NULL,
    origen origen_uso NOT NULL DEFAULT 'ia',
    fecha_inicio TIMESTAMPTZ NOT NULL,
    fecha_fin TIMESTAMPTZ,
    duracion_segundos INTEGER CHECK (duracion_segundos IS NULL OR duracion_segundos >= 0),
    confianza_promedio NUMERIC(5,4) CHECK (
        confianza_promedio IS NULL OR (confianza_promedio >= 0 AND confianza_promedio <= 1)
    ),
    cantidad_eventos INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_eventos >= 0),
    evento_inicio_uuid UUID,
    evento_fin_uuid UUID,
    estado VARCHAR(30) NOT NULL DEFAULT 'abierta'
        CHECK (estado IN ('abierta', 'cerrada', 'descartada')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_sesion_uso_fechas CHECK (
        fecha_fin IS NULL OR fecha_fin >= fecha_inicio
    )
);

CREATE INDEX IF NOT EXISTS ix_sesiones_uso_equipo_fecha
ON sesiones_uso(equipo_id, fecha_inicio DESC);

CREATE INDEX IF NOT EXISTS ix_sesiones_uso_camara_fecha
ON sesiones_uso(camara_id, fecha_inicio DESC);

CREATE INDEX IF NOT EXISTS ix_sesiones_uso_estado
ON sesiones_uso(estado);

-- ---------- RESUMEN DE EVENTOS IA ----------
-- Puente entre PostgreSQL y MongoDB.
-- Guarda solo metadatos consultables; el documento completo vive en MongoDB.
CREATE TABLE IF NOT EXISTS eventos_ia_resumen (
    id BIGSERIAL PRIMARY KEY,
    evento_uuid UUID NOT NULL UNIQUE,
    equipo_id BIGINT REFERENCES equipos(id) ON DELETE SET NULL,
    camara_id BIGINT NOT NULL REFERENCES camaras(id) ON DELETE RESTRICT,
    modelo_ia_id BIGINT REFERENCES modelos_ia(id) ON DELETE SET NULL,
    sesion_uso_id BIGINT REFERENCES sesiones_uso(id) ON DELETE SET NULL,
    tipo_evento tipo_evento_ia NOT NULL,
    timestamp_evento TIMESTAMPTZ NOT NULL,
    confidence NUMERIC(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    mongo_collection VARCHAR(80) NOT NULL DEFAULT 'eventos_ia',
    snapshot_url VARCHAR(700),
    clip_url VARCHAR(700),
    procesado BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_eventos_ia_resumen_camara_fecha
ON eventos_ia_resumen(camara_id, timestamp_evento DESC);

CREATE INDEX IF NOT EXISTS ix_eventos_ia_resumen_equipo_fecha
ON eventos_ia_resumen(equipo_id, timestamp_evento DESC);

CREATE INDEX IF NOT EXISTS ix_eventos_ia_resumen_tipo_fecha
ON eventos_ia_resumen(tipo_evento, timestamp_evento DESC);

-- ---------- AUDITORIA / REGISTRO DE ACCIONES ----------
CREATE TABLE IF NOT EXISTS registros_auditoria (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT REFERENCES empresas(id) ON DELETE SET NULL,
    sucursal_id BIGINT REFERENCES sucursales(id) ON DELETE SET NULL,
    actor VARCHAR(160),
    actor_tipo VARCHAR(40) NOT NULL DEFAULT 'sistema'
        CHECK (actor_tipo IN ('usuario', 'tecnico', 'sistema', 'ia')),
    accion VARCHAR(120) NOT NULL,
    entidad VARCHAR(100) NOT NULL,
    entidad_id VARCHAR(100),
    datos_anteriores JSONB,
    datos_nuevos JSONB,
    ip_origen INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_auditoria_entidad
ON registros_auditoria(entidad, entidad_id);

CREATE INDEX IF NOT EXISTS ix_auditoria_created_at
ON registros_auditoria(created_at DESC);

-- ---------- TRIGGERS UPDATED_AT ----------
DROP TRIGGER IF EXISTS trg_empresas_updated_at ON empresas;
CREATE TRIGGER trg_empresas_updated_at
BEFORE UPDATE ON empresas
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_sucursales_updated_at ON sucursales;
CREATE TRIGGER trg_sucursales_updated_at
BEFORE UPDATE ON sucursales
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_zonas_updated_at ON zonas;
CREATE TRIGGER trg_zonas_updated_at
BEFORE UPDATE ON zonas
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_equipos_updated_at ON equipos;
CREATE TRIGGER trg_equipos_updated_at
BEFORE UPDATE ON equipos
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_camaras_updated_at ON camaras;
CREATE TRIGGER trg_camaras_updated_at
BEFORE UPDATE ON camaras
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_incidencias_updated_at ON incidencias;
CREATE TRIGGER trg_incidencias_updated_at
BEFORE UPDATE ON incidencias
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_mantenimientos_updated_at ON mantenimientos;
CREATE TRIGGER trg_mantenimientos_updated_at
BEFORE UPDATE ON mantenimientos
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_sesiones_uso_updated_at ON sesiones_uso;
CREATE TRIGGER trg_sesiones_uso_updated_at
BEFORE UPDATE ON sesiones_uso
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------- TRIGGER DURACION ----------
DROP TRIGGER IF EXISTS trg_sesiones_uso_duracion ON sesiones_uso;
CREATE TRIGGER trg_sesiones_uso_duracion
BEFORE INSERT OR UPDATE OF fecha_inicio, fecha_fin ON sesiones_uso
FOR EACH ROW EXECUTE FUNCTION set_duracion_sesion_uso();

-- ---------- TRIGGER RESOLUCION INCIDENCIA ----------
DROP TRIGGER IF EXISTS trg_incidencias_fecha_resolucion ON incidencias;
CREATE TRIGGER trg_incidencias_fecha_resolucion
BEFORE UPDATE OF estado ON incidencias
FOR EACH ROW EXECUTE FUNCTION set_fecha_resolucion_incidencia();

-- ---------- VISTAS UTILES ----------
CREATE OR REPLACE VIEW vw_estado_equipos AS
SELECT
    e.id AS equipo_id,
    e.codigo_activo,
    e.nombre AS equipo,
    e.estado,
    s.id AS sucursal_id,
    s.nombre AS sucursal,
    em.id AS empresa_id,
    COALESCE(em.nombre_fantasia, em.razon_social) AS empresa,
    z.nombre AS zona,
    COUNT(i.id) FILTER (WHERE i.estado IN ('pendiente','en_proceso')) AS incidencias_abiertas,
    COUNT(i.id) FILTER (WHERE i.prioridad = 'urgente' AND i.estado IN ('pendiente','en_proceso')) AS urgentes_abiertas
FROM equipos e
JOIN sucursales s ON s.id = e.sucursal_id
JOIN empresas em ON em.id = s.empresa_id
LEFT JOIN zonas z ON z.id = e.zona_id
LEFT JOIN incidencias i ON i.equipo_id = e.id
GROUP BY e.id, e.codigo_activo, e.nombre, e.estado,
         s.id, s.nombre, em.id, em.nombre_fantasia, em.razon_social, z.nombre;

CREATE OR REPLACE VIEW vw_uso_diario_equipos AS
SELECT
    equipo_id,
    DATE(fecha_inicio) AS fecha,
    COUNT(*) FILTER (WHERE estado = 'cerrada') AS sesiones,
    COALESCE(SUM(duracion_segundos) FILTER (WHERE estado = 'cerrada'), 0) AS segundos_uso,
    ROUND(
        COALESCE(AVG(confianza_promedio) FILTER (WHERE estado = 'cerrada'), 0)::numeric,
        4
    ) AS confianza_promedio
FROM sesiones_uso
GROUP BY equipo_id, DATE(fecha_inicio);

-- ---------- DATOS BASE ----------
INSERT INTO tipos_falla (codigo, nombre, descripcion, prioridad_base, permite_reporte_qr, permite_deteccion_ia)
VALUES
    ('DESGASTE', 'Desgaste visible', 'Desgaste visible de piezas o componentes.', 'baja', TRUE, TRUE),
    ('SONIDO_EXTRANO', 'Sonido extraño', 'Ruido o vibración no habitual durante el uso.', 'media', TRUE, TRUE),
    ('ROTA', 'Pieza rota / no funciona', 'Equipo con daño físico o incapaz de operar correctamente.', 'urgente', TRUE, TRUE),
    ('NO_ENCIENDE', 'No enciende', 'Equipo eléctrico/electrónico no inicia.', 'urgente', TRUE, TRUE),
    ('MOVIMIENTO_ANOMALO', 'Movimiento anómalo', 'La IA detecta un patrón mecánico o de uso anómalo.', 'alta', FALSE, TRUE),
    ('OTRO', 'Otro', 'Falla no clasificada.', 'media', TRUE, FALSE)
ON CONFLICT (codigo) DO NOTHING;
