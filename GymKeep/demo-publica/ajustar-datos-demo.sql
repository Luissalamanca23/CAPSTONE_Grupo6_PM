-- ============================================================================
-- ajustar-datos-demo.sql
--
-- Ajuste de presentacion de los reportes que cargan reset_demo_incidencias.sql y
-- agregar_mas_datos.sql. Esos scripts dejan ~60 reportes casi todos de los ultimos 45 dias y
-- todos a la misma hora del dia, lo que en el Panel se ve como:
--   * un pico falso en la ultima semana ("1800 % mas que el periodo anterior"),
--   * la misma hora en todas las filas de las tablas y un pico falso en el mapa de calor,
--   * decenas de incidencias abiertas desde hace semanas.
--
-- Que hace (solo con reportes SIN marca "demo", es decir, los de esos dos scripts):
--   1. Reparte sus fechas en los ultimos 100 dias y su hora entre las 07:00 y las 22:00.
--   2. Los que quedan abiertos desde hace mas de 21 dias pasan a "resuelta" (un gimnasio real
--      no deja una falla sin atender 3 meses); su resolucion cae 1-9 dias despues del reporte.
--   3. Mueve junto con cada reporte las mantenciones que ya tuviera, para que no queden antes.
--
-- Correr ANTES de datos_demo_dashboard.sql (ese script completa cada semana hasta ~5 reportes
-- descontando los que ya existen, asi que la linea de tiempo queda pareja). Se marca cada fila
-- ya ajustada, por lo que correrlo otra vez no cambia nada.
-- ============================================================================
\set ON_ERROR_STOP on
BEGIN;
SELECT setseed(0.58);

CREATE TEMP TABLE tmp_aj ON COMMIT DROP AS
SELECT i.id, i.estado, i.fecha_reporte AS antes, i.fecha_resolucion AS res_antes,
       (date_trunc('day', i.fecha_reporte AT TIME ZONE 'America/Santiago')
         - floor(random() * 100) * interval '1 day'
         + interval '7 hours' + random() * interval '15 hours') AT TIME ZONE 'America/Santiago' AS nueva_bruta
FROM incidencias i
WHERE COALESCE(i.metadata ->> 'demo', '') = ''
  AND COALESCE(i.metadata ->> 'fechas', '') <> 'repartidas';

CREATE TEMP TABLE tmp_aj2 ON COMMIT DROP AS
SELECT a.*,
       LEAST(a.nueva_bruta, now() - interval '1 hour' - random() * interval '4 hours') AS nueva
FROM tmp_aj a;

-- Las mantenciones se mueven con su reporte.
UPDATE mantenimientos m
SET fecha_inicio = m.fecha_inicio + (a.nueva - a.antes),
    fecha_fin    = m.fecha_fin + (a.nueva - a.antes),
    created_at   = m.created_at + (a.nueva - a.antes),
    updated_at   = m.updated_at + (a.nueva - a.antes)
FROM tmp_aj2 a
WHERE m.incidencia_id = a.id;

UPDATE incidencias i
SET fecha_reporte = a.nueva,
    created_at = a.nueva,
    -- La resolucion depende del estado (algunos scripts dejan fecha_resolucion en reportes abiertos).
    fecha_resolucion = CASE
        WHEN a.estado IN ('resuelta', 'descartada') THEN LEAST(now(), a.nueva + COALESCE(a.res_antes - a.antes, interval '2 days'))
        WHEN a.nueva < now() - interval '21 days' THEN LEAST(now(), a.nueva + (1 + random() * 8) * interval '1 day')
    END,
    estado = CASE
        WHEN a.estado IN ('pendiente', 'en_proceso') AND a.nueva < now() - interval '21 days' THEN 'resuelta'::estado_incidencia
        ELSE i.estado
    END,
    metadata = i.metadata || '{"fechas": "repartidas"}'::jsonb
FROM tmp_aj2 a
WHERE i.id = a.id;

COMMIT;
