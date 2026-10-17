-- Vistas legibles para mirar la base en un visor (Adminer, DBeaver, pgAdmin).
--
-- Cada vista junta las tablas relacionadas y deja los datos listos para leer: nombres en vez de
-- ids, fechas en hora de Chile, montos en pesos con puntos, duraciones en horas y minutos y
-- estados con mayuscula inicial. Son solo para MIRAR (no se escribe en ellas); la aplicacion
-- sigue usando las tablas de siempre. Se pueden volver a ejecutar sin problema.
--
--   docker compose exec -T db psql -U gymkeep -d gymkeep < postgres/vistas_legibles.sql
--   (PowerShell: Get-Content postgres\vistas_legibles.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep)

-- ---------- EQUIPOS ----------
CREATE OR REPLACE VIEW v_equipos AS
SELECT
    e.id                                                        AS "Id",
    e.codigo_activo                                             AS "Código",
    e.nombre                                                    AS "Equipo",
    initcap(coalesce(e.categoria, '-'))                         AS "Categoría",
    concat_ws(' ', e.marca, e.modelo)                           AS "Marca y modelo",
    s.nombre                                                    AS "Sucursal",
    coalesce(z.nombre, '-')                                     AS "Zona",
    upper(left(replace(e.estado::text, '_', ' '), 1)) || substr(replace(e.estado::text, '_', ' '), 2)                  AS "Estado",
    to_char(e.fecha_instalacion, 'DD-MM-YYYY')                  AS "Instalado",
    coalesce(i.abiertas, 0)                                     AS "Incidencias abiertas",
    coalesce(i.total, 0)                                        AS "Incidencias totales",
    coalesce(m.total, 0)                                        AS "Mantenciones",
    '$ ' || replace(to_char(round(coalesce(m.costo, 0)), 'FM999,999,999,999'), ',', '.') AS "Costo en mantención",
    round(coalesce(u.segundos, 0) / 3600.0, 1)                  AS "Horas de uso"
FROM equipos e
JOIN sucursales s ON s.id = e.sucursal_id
LEFT JOIN zonas z ON z.id = e.zona_id
LEFT JOIN LATERAL (
    SELECT count(*) AS total,
           count(*) FILTER (WHERE estado IN ('pendiente', 'en_proceso')) AS abiertas
    FROM incidencias WHERE equipo_id = e.id
) i ON TRUE
LEFT JOIN LATERAL (
    SELECT count(*) AS total, sum(costo_total) AS costo
    FROM mantenimientos WHERE equipo_id = e.id
) m ON TRUE
LEFT JOIN LATERAL (
    SELECT sum(duracion_segundos) AS segundos
    FROM sesiones_uso WHERE equipo_id = e.id AND estado <> 'descartada'
) u ON TRUE
ORDER BY e.codigo_activo;

-- ---------- INCIDENCIAS ----------
CREATE OR REPLACE VIEW v_incidencias AS
SELECT
    i.id                                                        AS "Id",
    to_char(i.fecha_reporte AT TIME ZONE 'America/Santiago', 'DD-MM-YYYY HH24:MI') AS "Reportada",
    e.codigo_activo || ' · ' || e.nombre                        AS "Equipo",
    t.nombre                                                    AS "Falla",
    initcap(i.prioridad::text)                                  AS "Prioridad",
    upper(left(replace(i.estado::text, '_', ' '), 1)) || substr(replace(i.estado::text, '_', ' '), 2)                  AS "Estado",
    upper(i.origen::text)                                       AS "Origen",
    coalesce(i.reportado_por, '-')                              AS "Reportada por",
    coalesce(i.descripcion, '')                                 AS "Descripción",
    to_char(i.fecha_resolucion AT TIME ZONE 'America/Santiago', 'DD-MM-YYYY HH24:MI') AS "Resuelta",
    round(extract(epoch FROM (coalesce(i.fecha_resolucion, now()) - i.fecha_reporte)) / 86400.0, 1) AS "Días abierta"
FROM incidencias i
JOIN equipos e ON e.id = i.equipo_id
JOIN tipos_falla t ON t.id = i.tipo_falla_id
ORDER BY i.fecha_reporte DESC;

-- ---------- MANTENCIONES ----------
CREATE OR REPLACE VIEW v_mantenimientos AS
SELECT
    m.id                                                        AS "Id",
    to_char(m.fecha_inicio AT TIME ZONE 'America/Santiago', 'DD-MM-YYYY') AS "Fecha",
    e.codigo_activo || ' · ' || e.nombre                        AS "Equipo",
    initcap(m.tipo)                                             AS "Tipo",
    coalesce(m.tecnico, '-')                                    AS "Técnico",
    coalesce(m.proveedor, '-')                                  AS "Proveedor",
    m.descripcion                                               AS "Descripción",
    CASE WHEN m.costo_total IS NULL THEN '-'
         ELSE '$ ' || replace(to_char(round(m.costo_total), 'FM999,999,999,999'), ',', '.') END AS "Costo",
    CASE WHEN m.fecha_fin IS NULL THEN 'En curso'
         ELSE greatest(1, round(extract(epoch FROM (m.fecha_fin - m.fecha_inicio)) / 3600.0))::int || ' h' END AS "Duración",
    to_char(m.proximo_mantenimiento, 'DD-MM-YYYY')              AS "Próxima",
    m.incidencia_id                                             AS "Incidencia"
FROM mantenimientos m
JOIN equipos e ON e.id = m.equipo_id
ORDER BY m.fecha_inicio DESC;

-- ---------- SESIONES DE USO ----------
CREATE OR REPLACE VIEW v_sesiones_uso AS
SELECT
    su.id                                                       AS "Id",
    e.codigo_activo || ' · ' || e.nombre                        AS "Equipo",
    coalesce(c.codigo, '-')                                     AS "Cámara",
    to_char(su.fecha_inicio AT TIME ZONE 'America/Santiago', 'DD-MM-YYYY HH24:MI:SS') AS "Inicio",
    to_char(su.fecha_fin AT TIME ZONE 'America/Santiago', 'DD-MM-YYYY HH24:MI:SS')    AS "Fin",
    CASE WHEN su.duracion_segundos IS NULL THEN '-'
         WHEN su.duracion_segundos >= 3600 THEN (su.duracion_segundos / 3600) || ' h ' || lpad(((su.duracion_segundos % 3600) / 60)::text, 2, '0') || ' min'
         ELSE (su.duracion_segundos / 60) || ' min ' || lpad((su.duracion_segundos % 60)::text, 2, '0') || ' s' END AS "Duración",
    CASE WHEN su.confianza_promedio IS NULL THEN '-'
         ELSE round(su.confianza_promedio * 100)::int || ' %' END AS "Confianza",
    initcap(su.estado)                                          AS "Estado",
    upper(su.origen::text)                                      AS "Origen"
FROM sesiones_uso su
JOIN equipos e ON e.id = su.equipo_id
LEFT JOIN camaras c ON c.id = su.camara_id
ORDER BY su.fecha_inicio DESC;

-- ---------- CAMARAS ----------
CREATE OR REPLACE VIEW v_camaras AS
SELECT
    c.id                                                        AS "Id",
    c.codigo                                                    AS "Código",
    c.nombre                                                    AS "Cámara",
    s.nombre                                                    AS "Sucursal",
    coalesce(z.nombre, '-')                                     AS "Zona",
    initcap(c.estado::text)                                     AS "Estado",
    CASE WHEN c.ancho_px IS NULL THEN '-' ELSE c.ancho_px || ' x ' || c.alto_px END AS "Resolución",
    coalesce(round(c.fps_configurado)::text, '-')               AS "FPS",
    to_char(c.ultima_conexion AT TIME ZONE 'America/Santiago', 'DD-MM-YYYY HH24:MI:SS') AS "Última conexión",
    (SELECT count(*) FROM camara_equipos ce WHERE ce.camara_id = c.id AND ce.activo) AS "Máquinas con zona"
FROM camaras c
JOIN sucursales s ON s.id = c.sucursal_id
LEFT JOIN zonas z ON z.id = c.zona_id
ORDER BY c.codigo;

-- ---------- COSTOS POR MES ----------
CREATE OR REPLACE VIEW v_costos_por_mes AS
SELECT
    to_char(date_trunc('month', m.fecha_inicio AT TIME ZONE 'America/Santiago'), 'YYYY-MM') AS "Mes",
    initcap(m.tipo)                                             AS "Tipo",
    count(*)                                                    AS "Mantenciones",
    '$ ' || replace(to_char(round(coalesce(sum(m.costo_total), 0)), 'FM999,999,999,999'), ',', '.') AS "Costo total"
FROM mantenimientos m
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
