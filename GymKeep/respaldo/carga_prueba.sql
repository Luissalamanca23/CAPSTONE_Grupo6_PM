-- DATOS DE PRUEBA para la prueba de restauracion con una base grande (RNF-21).
-- Todo lo que crea lleva la marca ZZPRUEBA- (equipos) o prueba_carga (metadata): carga_prueba_limpiar.sql
-- lo borra por completo. Lo corre prueba-restauracion-grande.bat; no ejecutar en una base con datos reales.
-- Volumen: 3.000 equipos, 300.000 sesiones de uso, 30.000 mantenciones y 15.000 incidencias resueltas
-- (las incidencias son resueltas y antiguas a proposito: no disparan avisos emergentes).
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM equipos WHERE codigo_activo LIKE 'ZZPRUEBA-%') THEN
        RAISE EXCEPTION 'Ya hay datos de prueba cargados (ZZPRUEBA-*). Ejecuta primero carga_prueba_limpiar.sql.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM sucursales) OR NOT EXISTS (SELECT 1 FROM tipos_falla) THEN
        RAISE EXCEPTION 'Falta una sucursal o un tipo de falla en la base.';
    END IF;
END $$;

INSERT INTO equipos (sucursal_id, codigo_activo, nombre, categoria, marca, modelo, costo_adquisicion, estado, observaciones)
SELECT (SELECT id FROM sucursales ORDER BY id LIMIT 1),
       'ZZPRUEBA-' || lpad(g::text, 5, '0'),
       'Equipo de prueba ' || g,
       'cardio', 'PruebaFit', 'Modelo-' || (g % 20),
       500000 + (g % 50) * 10000,
       'operativo',
       'DATOS DE PRUEBA para RNF-21: se borran al terminar.'
FROM generate_series(1, 3000) g;

INSERT INTO sesiones_uso (equipo_id, origen, fecha_inicio, fecha_fin, duracion_segundos, confianza_promedio, cantidad_eventos, estado, metadata)
SELECT e.id, 'manual',
       NOW() - make_interval(secs => n * 1800 + (e.id % 600)),
       NOW() - make_interval(secs => n * 1800 + (e.id % 600)) + make_interval(secs => 900 + (n % 300)),
       900 + (n % 300), 0.9, 3, 'cerrada', '{"prueba_carga": true}'::jsonb
FROM equipos e CROSS JOIN generate_series(1, 100) n
WHERE e.codigo_activo LIKE 'ZZPRUEBA-%';

INSERT INTO mantenimientos (equipo_id, tipo, tecnico, descripcion, repuestos, costo_total, fecha_inicio, fecha_fin)
SELECT e.id, (ARRAY['preventivo', 'correctivo', 'inspeccion'])[1 + (n % 3)],
       'Tecnico de prueba', 'Mantencion de prueba ' || n, '[]'::jsonb, 10000 + n * 500,
       NOW() - make_interval(days => n * 20),
       NOW() - make_interval(days => n * 20) + interval '2 hours'
FROM equipos e CROSS JOIN generate_series(1, 10) n
WHERE e.codigo_activo LIKE 'ZZPRUEBA-%';

INSERT INTO incidencias (equipo_id, tipo_falla_id, origen, descripcion, reportado_por, prioridad, estado, fecha_reporte, metadata)
SELECT e.id, (SELECT id FROM tipos_falla ORDER BY id LIMIT 1), 'tecnico',
       'Incidencia de prueba ' || n, 'Prueba de carga', 'baja', 'resuelta',
       NOW() - make_interval(days => 60 + n), '{"prueba_carga": true}'::jsonb
FROM equipos e CROSS JOIN generate_series(1, 5) n
WHERE e.codigo_activo LIKE 'ZZPRUEBA-%';

COMMIT;

SELECT (SELECT count(*) FROM equipos WHERE codigo_activo LIKE 'ZZPRUEBA-%') AS equipos_de_prueba,
       (SELECT count(*) FROM sesiones_uso) AS sesiones_en_total,
       (SELECT count(*) FROM mantenimientos) AS mantenciones_en_total,
       (SELECT count(*) FROM incidencias) AS incidencias_en_total,
       pg_size_pretty(pg_database_size(current_database())) AS tamano_de_la_base;
