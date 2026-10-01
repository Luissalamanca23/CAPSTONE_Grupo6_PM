-- ============================================================================
-- agregar_mas_datos.sql
--
-- Que hace (todo ADITIVO, no borra nada de lo que ya tienes):
--   1) Normaliza el origen de TODAS las incidencias existentes a 'qr', porque
--      por ahora el unico canal real de reporte es el codigo QR.
--   2) Agrega 10 maquinas nuevas (EQ-0016 a EQ-0025), repartidas en las zonas
--      ya existentes del mismo gimnasio (Cardio / Fuerza / Funcional / Peso Libre).
--   3) Les genera QR activo a las maquinas nuevas (y a cualquier otra que le falte).
--   4) Agrega 30 incidencias nuevas, TODAS con origen = 'qr' (ya no se usan
--      'ia' / 'tecnico' / 'sistema'), y solo con tipos de falla que el catalogo
--      permite reportar por QR (no se usa "Movimiento anomalo", que es
--      exclusivo de deteccion por IA). Fechas repartidas entre hoy y ~45 dias
--      atras para que los filtros de fecha tengan variedad.
--
-- Como ejecutarlo (PowerShell, con Docker ya levantado):
--   Get-Content postgres\agregar_mas_datos.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
--
-- Es seguro correrlo mas de una vez: los equipos usan ON CONFLICT DO NOTHING,
-- y cada corrida simplemente agrega 30 incidencias nuevas mas.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Normalizar el origen de las incidencias que ya existen
-- ---------------------------------------------------------------------------
UPDATE incidencias SET origen = 'qr'::origen_incidencia WHERE origen <> 'qr';

-- ---------------------------------------------------------------------------
-- 2) Maquinas nuevas, en el mismo (unico) gimnasio
-- ---------------------------------------------------------------------------
INSERT INTO equipos (sucursal_id, zona_id, codigo_activo, nombre, categoria, marca, modelo, estado)
SELECT s.id, z.id, v.codigo_activo, v.nombre, v.categoria, v.marca, v.modelo, v.estado::estado_equipo
FROM (
    VALUES
        ('EQ-0016', 'Cinta de correr 04',          'cardio',    'DemoFit',  'Run-X',   'Cardio',     'operativo'),
        ('EQ-0017', 'Bicicleta estatica 03',       'cardio',    'DemoFit',  'Cycle-S', 'Cardio',     'operativo'),
        ('EQ-0018', 'Escaladora 01',                'cardio',    'DemoFit',  'Climb-1', 'Cardio',     'operativo'),
        ('EQ-0019', 'Remo 02',                      'cardio',    'DemoFit',  'Row-1',   'Cardio',     'en_mantenimiento'),
        ('EQ-0020', 'Prensa de piernas 01',         'fuerza',    'IronCore', 'PP-150',  'Fuerza',     'operativo'),
        ('EQ-0021', 'Jaula de crossfit 01',         'fuerza',    'IronCore', 'JC-900',  'Fuerza',     'operativo'),
        ('EQ-0022', 'Set de barras olimpicas',      'peso_libre','IronCore', 'BO-20',   'Peso Libre', 'operativo'),
        ('EQ-0023', 'Set de kettlebells',           'peso_libre','IronCore', 'KB-01',   'Peso Libre', 'operativo'),
        ('EQ-0024', 'Colchonetas funcionales',      'funcional', 'DemoFit',  'MAT-10',  'Funcional',  'operativo'),
        ('EQ-0025', 'Bandas de suspension TRX',     'funcional', 'DemoFit',  'TRX-1',   'Funcional',  'fuera_de_servicio')
) AS v(codigo_activo, nombre, categoria, marca, modelo, zona_nombre, estado)
JOIN sucursales s ON s.id = (SELECT id FROM sucursales ORDER BY id LIMIT 1)
JOIN zonas z ON z.sucursal_id = s.id AND z.nombre = v.zona_nombre
ON CONFLICT (sucursal_id, codigo_activo) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3) QR activo para cualquier equipo que aun no tenga uno
-- ---------------------------------------------------------------------------
INSERT INTO qr_equipos (equipo_id)
SELECT e.id
FROM equipos e
WHERE NOT EXISTS (
    SELECT 1 FROM qr_equipos q WHERE q.equipo_id = e.id AND q.activo = TRUE
);

-- ---------------------------------------------------------------------------
-- 4) Incidencias nuevas, todas via QR
-- ---------------------------------------------------------------------------
INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por,
    prioridad, estado, fecha_reporte, fecha_resolucion
)
SELECT
    e.id,
    tf.id,
    'qr'::origen_incidencia,
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
        ('EQ-0016', 'DESGASTE',       NULL, 'Camila Rojas',    'baja',    'pendiente',   0,  NULL),
        ('EQ-0016', 'SONIDO_EXTRANO', NULL, 'Camila Rojas',    'media',   'en_proceso',  3,  NULL),
        ('EQ-0017', 'ROTA',           NULL, 'Matias Vega',     'urgente', 'pendiente',   0,  NULL),
        ('EQ-0017', 'NO_ENCIENDE',    NULL, 'Matias Vega',     'urgente', 'resuelta',    22, 2),
        ('EQ-0018', 'OTRO',           'Pantalla de la escaladora se congela a mitad de la rutina.', 'Camila Rojas', 'media', 'pendiente', 1, NULL),
        ('EQ-0018', 'DESGASTE',       NULL, 'Matias Vega',     'baja',    'en_proceso',  6,  NULL),
        ('EQ-0019', 'SONIDO_EXTRANO', NULL, 'Fernanda Castro', 'media',   'pendiente',   0,  NULL),
        ('EQ-0019', 'ROTA',           NULL, 'Fernanda Castro', 'urgente', 'resuelta',    28, 3),
        ('EQ-0020', 'NO_ENCIENDE',    NULL, 'Ignacio Soto',    'urgente', 'pendiente',   0,  NULL),
        ('EQ-0020', 'OTRO',           'Asiento suelto, se mueve al usar la maquina.', 'Ignacio Soto', 'media', 'descartada', 11, NULL),
        ('EQ-0021', 'DESGASTE',       NULL, 'Fernanda Castro', 'baja',    'pendiente',   2,  NULL),
        ('EQ-0021', 'SONIDO_EXTRANO', NULL, 'Ignacio Soto',    'media',   'en_proceso',  4,  NULL),
        ('EQ-0022', 'ROTA',           NULL, 'Camila Rojas',    'urgente', 'pendiente',   0,  NULL),
        ('EQ-0022', 'OTRO',           'Falta una de las barras del set.', 'Camila Rojas', 'media', 'resuelta', 35, 4),
        ('EQ-0023', 'NO_ENCIENDE',    NULL, 'Matias Vega',     'urgente', 'en_proceso',  1,  NULL),
        ('EQ-0023', 'DESGASTE',       NULL, 'Matias Vega',     'baja',    'descartada',  14, NULL),
        ('EQ-0024', 'SONIDO_EXTRANO', NULL, 'Fernanda Castro', 'media',   'pendiente',   0,  NULL),
        ('EQ-0024', 'ROTA',           NULL, 'Fernanda Castro', 'urgente', 'pendiente',   5,  NULL),
        ('EQ-0025', 'NO_ENCIENDE',    NULL, 'Ignacio Soto',    'urgente', 'resuelta',    40, 2),
        ('EQ-0025', 'OTRO',           'Correa de suspension deshilachada.', 'Ignacio Soto', 'media', 'en_proceso', 2, NULL),
        ('EQ-0001', 'OTRO',           'Base inestable al correr a alta velocidad.', 'Camila Rojas', 'media', 'pendiente', 0, NULL),
        ('EQ-0002', 'SONIDO_EXTRANO', NULL, 'Matias Vega',     'media',   'pendiente',   1,  NULL),
        ('EQ-0006', 'DESGASTE',       NULL, 'Fernanda Castro', 'baja',    'en_proceso',  3,  NULL),
        ('EQ-0010', 'ROTA',           NULL, 'Ignacio Soto',    'urgente', 'pendiente',   0,  NULL),
        ('EQ-0014', 'NO_ENCIENDE',    NULL, 'Camila Rojas',    'urgente', 'resuelta',    45, 3),
        ('02',      'DESGASTE',       NULL, 'Matias Vega',     'baja',    'pendiente',   0,  NULL),
        ('02',      'OTRO',           'Cable de la polea rozando contra el marco.', 'Matias Vega', 'media', 'en_proceso', 6, NULL),
        ('03',      'SONIDO_EXTRANO', NULL, 'Fernanda Castro', 'media',   'pendiente',   2,  NULL),
        ('03',      'ROTA',           NULL, 'Fernanda Castro', 'urgente', 'resuelta',    20, 2),
        ('EQ-0011', 'NO_ENCIENDE',    NULL, 'Ignacio Soto',    'urgente', 'pendiente',   0,  NULL)
) AS v(codigo_activo, tipo_falla_codigo, descripcion, reportado_por, prioridad, estado, dias_atras, dias_resolucion)
JOIN equipos e ON e.codigo_activo = v.codigo_activo
JOIN tipos_falla tf ON tf.codigo = v.tipo_falla_codigo;

COMMIT;

-- ---------------------------------------------------------------------------
-- Resumen
-- ---------------------------------------------------------------------------
SELECT 'equipos totales' AS detalle, COUNT(*) AS cantidad FROM equipos
UNION ALL
SELECT 'incidencias totales', COUNT(*) FROM incidencias
UNION ALL
SELECT 'incidencias con origen distinto de qr (deberia ser 0)', COUNT(*) FROM incidencias WHERE origen <> 'qr';
