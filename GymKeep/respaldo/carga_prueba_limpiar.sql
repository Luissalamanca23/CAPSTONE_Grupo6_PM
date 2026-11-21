-- Borra TODO lo que creo carga_prueba.sql (y solo eso: equipos ZZPRUEBA-* y sus filas).
BEGIN;
DELETE FROM sesiones_uso   WHERE equipo_id IN (SELECT id FROM equipos WHERE codigo_activo LIKE 'ZZPRUEBA-%');
DELETE FROM mantenimientos WHERE equipo_id IN (SELECT id FROM equipos WHERE codigo_activo LIKE 'ZZPRUEBA-%');
DELETE FROM incidencias    WHERE equipo_id IN (SELECT id FROM equipos WHERE codigo_activo LIKE 'ZZPRUEBA-%');
DELETE FROM equipos        WHERE codigo_activo LIKE 'ZZPRUEBA-%';
COMMIT;

SELECT (SELECT count(*) FROM equipos WHERE codigo_activo LIKE 'ZZPRUEBA-%') AS equipos_de_prueba_que_quedan,
       (SELECT count(*) FROM sesiones_uso) AS sesiones_en_total,
       pg_size_pretty(pg_database_size(current_database())) AS tamano_de_la_base;
