-- ============================================================================
-- reset_demo_incidencias.sql
--
-- Que hace:
--   1) Borra TODAS las incidencias actuales.
--   2) Agrega zonas nuevas (Fuerza, Funcional, Peso Libre) dentro del UNICO
--      gimnasio/sucursal que ya existe en el sistema (no crea una sucursal
--      nueva, asi que todo lo nuevo queda garantizado en el mismo gym).
--   3) Agrega equipos nuevos, todos repartidos en esas zonas + la zona Cardio
--      ya existente, con distintos "estado" (operativo / en_mantenimiento /
--      fuera_de_servicio / retirado) para poder ver los colores de salud.
--   4) Genera un QR activo para cualquier equipo (nuevo o viejo) que no tenga uno.
--   5) Inserta ~30 incidencias nuevas con la mayor variedad posible: los 6
--      tipos de falla del catalogo, las 4 prioridades, los 4 estados, los 4
--      origenes, y fechas repartidas entre hoy y hace 30 dias (para poder
--      probar los filtros de "hoy / esta semana / este mes / rango").
--
-- Como ejecutarlo (desde cmd, con Docker ya levantado):
--   docker compose exec -T db psql -U gymkeep -d gymkeep < postgres\reset_demo_incidencias.sql
--
-- Es seguro correrlo mas de una vez: usa ON CONFLICT DO NOTHING donde
-- corresponde, y las incidencias siempre se re-generan desde cero.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Borrar todas las incidencias actuales
-- ---------------------------------------------------------------------------
DELETE FROM incidencias;

-- ---------------------------------------------------------------------------
-- 2) Zonas nuevas dentro del unico gimnasio existente
-- ---------------------------------------------------------------------------
INSERT INTO zonas (sucursal_id, nombre, descripcion)
SELECT id, 'Fuerza', 'Zona de maquinas de fuerza y musculacion'
FROM sucursales ORDER BY id LIMIT 1
ON CONFLICT (sucursal_id, nombre) DO NOTHING;

INSERT INTO zonas (sucursal_id, nombre, descripcion)
SELECT id, 'Funcional', 'Zona de entrenamiento funcional y clases grupales'
FROM sucursales ORDER BY id LIMIT 1
ON CONFLICT (sucursal_id, nombre) DO NOTHING;

INSERT INTO zonas (sucursal_id, nombre, descripcion)
SELECT id, 'Peso Libre', 'Zona de pesas libres y mancuernas'
FROM sucursales ORDER BY id LIMIT 1
ON CONFLICT (sucursal_id, nombre) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3) Equipos nuevos, todos en la misma (unica) sucursal
-- ---------------------------------------------------------------------------
INSERT INTO equipos (sucursal_id, zona_id, codigo_activo, nombre, categoria, marca, modelo, estado)
SELECT s.id, z.id, v.codigo_activo, v.nombre, v.categoria, v.marca, v.modelo, v.estado::estado_equipo
FROM (
    VALUES
        ('EQ-0002', 'Cinta de correr 02',          'cardio',   'DemoFit',  'Run-X',    'Cardio',      'operativo'),
        ('EQ-0003', 'Bicicleta estatica 01',       'cardio',   'DemoFit',  'Cycle-S',  'Cardio',      'operativo'),
        ('EQ-0004', 'Eliptica 01',                 'cardio',   'DemoFit',  'Elip-2',   'Cardio',      'en_mantenimiento'),
        ('EQ-0005', 'Remo 01',                     'cardio',   'DemoFit',  'Row-1',    'Cardio',      'operativo'),
        ('EQ-0006', 'Multiestacion de fuerza 01',  'fuerza',   'IronCore', 'MS-500',   'Fuerza',      'operativo'),
        ('EQ-0007', 'Press de banca 01',           'fuerza',   'IronCore', 'PB-100',   'Fuerza',      'fuera_de_servicio'),
        ('EQ-0008', 'Rack de sentadillas 01',       'fuerza',   'IronCore', 'RS-200',   'Fuerza',      'operativo'),
        ('EQ-0009', 'Polea alta-baja 01',           'fuerza',   'IronCore', 'PL-300',   'Fuerza',      'operativo'),
        ('EQ-0010', 'Set de mancuernas 01',         'peso_libre','IronCore','MC-01',    'Peso Libre',  'operativo'),
        ('EQ-0011', 'Bicicleta de spinning 01',     'funcional','DemoFit',  'Spin-1',   'Funcional',   'operativo'),
        ('EQ-0012', 'Plataforma vibratoria 01',     'funcional','VibroTech','PV-10',    'Funcional',   'en_mantenimiento'),
        ('EQ-0013', 'Maquina de abdominales 01',    'funcional','IronCore', 'AB-40',    'Funcional',   'retirado'),
        ('EQ-0014', 'Cinta de correr 03',           'cardio',   'DemoFit',  'Run-X',    'Cardio',      'operativo'),
        ('EQ-0015', 'Bicicleta estatica 02',        'cardio',   'DemoFit',  'Cycle-S',  'Cardio',      'fuera_de_servicio')
) AS v(codigo_activo, nombre, categoria, marca, modelo, zona_nombre, estado)
JOIN sucursales s ON s.id = (SELECT id FROM sucursales ORDER BY id LIMIT 1)
JOIN zonas z ON z.sucursal_id = s.id AND z.nombre = v.zona_nombre
ON CONFLICT (sucursal_id, codigo_activo) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 4) QR activo para cualquier equipo (nuevo o viejo) que aun no tenga uno
-- ---------------------------------------------------------------------------
INSERT INTO qr_equipos (equipo_id)
SELECT e.id
FROM equipos e
WHERE NOT EXISTS (
    SELECT 1 FROM qr_equipos q WHERE q.equipo_id = e.id AND q.activo = TRUE
);

-- ---------------------------------------------------------------------------
-- 5) Incidencias nuevas, con la mayor variedad posible
-- ---------------------------------------------------------------------------
INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por,
    prioridad, estado, fecha_reporte, fecha_resolucion
)
SELECT
    e.id,
    tf.id,
    v.origen::origen_incidencia,
    COALESCE(v.descripcion, tf.descripcion),
    v.reportado_por,
    v.prioridad::prioridad_incidencia,
    v.estado::estado_incidencia,
    NOW() - (v.dias_atras || ' days')::interval,
    CASE
        WHEN v.dias_resolucion IS NOT NULL
        THEN NOW() - (v.dias_atras || ' days')::interval + (v.dias_resolucion || ' days')::interval
        ELSE NULL
    END
FROM (
    VALUES
        ('EQ-0001', 'DESGASTE',           'qr',       NULL, 'Juan Perez',         'baja',    'pendiente',   0,   NULL),
        ('EQ-0001', 'SONIDO_EXTRANO',     'qr',       NULL, 'Maria Lopez',        'media',   'en_proceso',  2,   NULL),
        ('EQ-0002', 'ROTA',               'qr',       NULL, 'Carlos Diaz',        'urgente', 'pendiente',   0,   NULL),
        ('EQ-0002', 'DESGASTE',           'tecnico',  NULL, 'Tecnico Soporte',    'baja',    'resuelta',    15,  2),
        ('EQ-0003', 'NO_ENCIENDE',        'qr',       NULL, 'Ana Torres',         'urgente', 'en_proceso',  1,   NULL),
        ('EQ-0003', 'MOVIMIENTO_ANOMALO', 'ia',       NULL, NULL,                 'alta',    'pendiente',   0,   NULL),
        ('EQ-0004', 'SONIDO_EXTRANO',     'sistema',  NULL, NULL,                 'media',   'pendiente',   3,   NULL),
        ('EQ-0004', 'ROTA',               'tecnico',  NULL, 'Tecnico Soporte',    'urgente', 'resuelta',    20,  1),
        ('EQ-0005', 'OTRO',               'qr',       'Reporte de olor extrano al usar el equipo.', 'Pedro Ramirez', 'media', 'descartada', 10, NULL),
        ('EQ-0005', 'DESGASTE',           'qr',       NULL, 'Pedro Ramirez',      'baja',    'en_proceso',  5,   NULL),
        ('EQ-0006', 'MOVIMIENTO_ANOMALO', 'ia',       NULL, NULL,                 'alta',    'en_proceso',  1,   NULL),
        ('EQ-0006', 'NO_ENCIENDE',        'tecnico',  NULL, 'Tecnico Soporte',    'urgente', 'pendiente',   0,   NULL),
        ('EQ-0007', 'ROTA',               'qr',       NULL, 'Sofia Munoz',        'urgente', 'pendiente',   0,   NULL),
        ('EQ-0007', 'SONIDO_EXTRANO',     'qr',       NULL, 'Sofia Munoz',        'media',   'resuelta',    25,  3),
        ('EQ-0008', 'DESGASTE',           'qr',       NULL, 'Diego Silva',        'baja',    'pendiente',   6,   NULL),
        ('EQ-0008', 'OTRO',               'tecnico',  'Ruido metalico intermitente en la polea.', 'Tecnico Soporte', 'media', 'en_proceso', 4, NULL),
        ('EQ-0009', 'MOVIMIENTO_ANOMALO', 'ia',       NULL, NULL,                 'alta',    'resuelta',    18,  2),
        ('EQ-0009', 'NO_ENCIENDE',        'qr',       NULL, 'Laura Fernandez',    'urgente', 'descartada',  8,   NULL),
        ('EQ-0010', 'DESGASTE',           'qr',       NULL, 'Laura Fernandez',    'baja',    'pendiente',   0,   NULL),
        ('EQ-0010', 'SONIDO_EXTRANO',     'sistema',  NULL, NULL,                 'media',   'pendiente',   2,   NULL),
        ('EQ-0011', 'ROTA',               'tecnico',  NULL, 'Tecnico Soporte',    'urgente', 'en_proceso',  1,   NULL),
        ('EQ-0011', 'OTRO',               'qr',       'Pedal suelto detectado por el usuario.', 'Diego Silva', 'media', 'resuelta', 30, 4),
        ('EQ-0012', 'MOVIMIENTO_ANOMALO', 'ia',       NULL, NULL,                 'alta',    'pendiente',   0,   NULL),
        ('EQ-0012', 'DESGASTE',           'qr',       NULL, 'Carlos Diaz',        'baja',    'resuelta',    12,  2),
        ('EQ-0013', 'NO_ENCIENDE',        'tecnico',  NULL, 'Tecnico Soporte',    'urgente', 'pendiente',   0,   NULL),
        ('EQ-0013', 'SONIDO_EXTRANO',     'qr',       NULL, 'Ana Torres',         'media',   'descartada',  9,   NULL),
        ('EQ-0014', 'OTRO',               'qr',       'Pantalla del panel parpadea al iniciar.', 'Maria Lopez', 'media', 'pendiente', 0, NULL),
        ('EQ-0014', 'DESGASTE',           'ia',       NULL, NULL,                 'baja',    'en_proceso',  7,   NULL),
        ('EQ-0015', 'ROTA',               'qr',       NULL, 'Juan Perez',         'urgente', 'pendiente',   0,   NULL),
        ('EQ-0015', 'MOVIMIENTO_ANOMALO', 'ia',       NULL, NULL,                 'alta',    'en_proceso',  3,   NULL)
) AS v(codigo_activo, tipo_falla_codigo, origen, descripcion, reportado_por, prioridad, estado, dias_atras, dias_resolucion)
JOIN equipos e ON e.codigo_activo = v.codigo_activo
JOIN tipos_falla tf ON tf.codigo = v.tipo_falla_codigo;

COMMIT;

-- ---------------------------------------------------------------------------
-- Resumen (se imprime al ejecutar el script)
-- ---------------------------------------------------------------------------
SELECT 'equipos totales' AS detalle, COUNT(*) AS cantidad FROM equipos
UNION ALL
SELECT 'incidencias totales', COUNT(*) FROM incidencias
UNION ALL
SELECT 'sucursales (gimnasios)', COUNT(*) FROM sucursales;
