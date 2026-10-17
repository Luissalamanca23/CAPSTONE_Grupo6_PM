-- ============================================================================
-- datos_demo_dashboard.sql
--
-- Historial de ~2 anos de incidencias, mantenciones y costos para que los
-- graficos del Panel (tendencias, gasto, rankings, mapa de calor) tengan sentido.
--
-- La logica que tienen los datos:
--   * Cada incidencia RESUELTA tiene su mantencion CORRECTIVA asociada
--     (mantenimientos.incidencia_id): empieza unas horas despues del reporte y
--     termina el dia que se resolvio la incidencia.
--   * El costo depende del tipo de falla: una pieza rota o un equipo que no
--     enciende cuesta mucho mas que un desgaste o un ruido.
--   * Las incidencias se concentran en horario punta (17-21 h, hora de Chile).
--   * Hay maquinas "problematicas" (EQ-0002, 0003, 0007, 0014, 0017) con
--     muchas mas fallas y casi sin mantencion preventiva: eso muestra el valor
--     de prevenir.
--   * El historial cubre ~2 anos (el Panel compara 8 semanas, 6 y 12 meses contra el
--     periodo anterior) y descuenta las incidencias que ya existen en cada semana
--     (otros scripts de demostracion), asi no se forman huecos ni picos raros.
--   * Hay mas fallas los lunes y martes (despues del fin de semana).
--   * Los tiempos de resolucion mejoran con los meses y las fallas suben un poco
--     hacia el presente.
--   * Las incidencias que ya estaban resueltas (de los otros scripts) tambien reciben
--     su mantencion correctiva con costo.
--   * Cada maquina sana tiene mantenciones PREVENTIVAS cada ~3 meses (cardio y
--     fuerza) o ~6 meses (funcional y peso libre), y algunas inspecciones.
--   * Las maquinas "en mantenimiento" tienen una mantencion abierta (sin fecha
--     de termino) y hay un par de incidencias urgentes sin atender hace dias,
--     para que se activen los avisos de "Atencion recomendada".
--
-- Como ejecutarlo (con Docker ya levantado y los scripts de equipos ya cargados:
-- seed.sql, reset_demo_incidencias.sql y agregar_mas_datos.sql):
--
--   Windows PowerShell:
--     Get-Content postgres\datos_demo_dashboard.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
--   Mac / Linux:
--     docker compose exec -T db psql -U gymkeep -d gymkeep < postgres/datos_demo_dashboard.sql
--
-- Es seguro correrlo mas de una vez: al empezar borra SOLO lo que creo una
-- corrida anterior (filas marcadas con "demo": "dashboard") y vuelve a
-- generarlo con fechas relativas a hoy. No toca nada que hayas creado a mano.
-- ============================================================================

BEGIN;

-- Misma "semilla" => mismos datos cada vez (solo se desplazan las fechas).
SELECT setseed(0.42);

-- ---------------------------------------------------------------------------
-- 0) Limpiar la corrida anterior (solo filas marcadas como demo)
-- ---------------------------------------------------------------------------
DELETE FROM mantenimientos WHERE repuestos @> '[{"demo": "dashboard"}]'::jsonb;
DELETE FROM incidencias    WHERE metadata  @> '{"demo": "dashboard"}'::jsonb;

-- ---------------------------------------------------------------------------
-- 1) Parametros por tipo de falla
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_cat ON COMMIT DROP AS
SELECT * FROM (
    VALUES
        (1, 'DESGASTE',       0.30,  15000,  55000,  48, 120,
            ARRAY['Cambio de correa de desgaste y lubricación', 'Reemplazo de almohadillas y revisión de tapiz', 'Ajuste de tensión y cambio de piezas desgastadas'],
            ARRAY['Correa de transmisión', 'Almohadilla', 'Kit de repuestos']),
        (2, 'SONIDO_EXTRANO', 0.52,  12000,  43000,   6,  42,
            ARRAY['Lubricación de rodamientos y ajuste de pernos', 'Cambio de rodamiento ruidoso', 'Limpieza y engrase de guías'],
            ARRAY['Rodamiento', 'Lubricante industrial', 'Pernos y fijaciones']),
        (3, 'ROTA',           0.66,  80000, 270000,  24,  96,
            ARRAY['Reemplazo de pieza estructural dañada', 'Cambio de cable de acero y poleas', 'Reparación de soldadura y refuerzo de soporte'],
            ARRAY['Pieza estructural', 'Cable de acero', 'Soporte reforzado']),
        (4, 'NO_ENCIENDE',    0.78,  60000, 200000,  12,  60,
            ARRAY['Cambio de fuente de poder', 'Reemplazo de tarjeta electrónica', 'Reparación de cableado y conector de alimentación'],
            ARRAY['Fuente de poder', 'Tarjeta electrónica', 'Conector de alimentación']),
        (5, 'OTRO',           1.00,  10000,  80000,   8,  88,
            ARRAY['Revisión general y ajustes menores', 'Reemplazo de consola o pantalla', 'Ajuste y fijación de componentes sueltos'],
            ARRAY['Insumos varios', 'Pantalla / consola', 'Fijaciones'])
) AS c(orden, codigo, acumulado, costo_min, costo_rango, horas_min, horas_rango, descripciones, repuestos);

-- ---------------------------------------------------------------------------
-- 2) Pool de maquinas: las "problematicas" pesan 5 veces mas que el resto
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_pool ON COMMIT DROP AS
SELECT row_number() OVER (ORDER BY e.id, g.n) AS k, e.id AS equipo_id
FROM equipos e
CROSS JOIN LATERAL generate_series(
    1,
    CASE WHEN e.codigo_activo IN ('EQ-0002', 'EQ-0003', 'EQ-0007', 'EQ-0014', 'EQ-0017') THEN 5 ELSE 1 END
) AS g(n)
WHERE e.codigo_activo LIKE 'EQ-%' AND e.estado <> 'retirado';

-- ---------------------------------------------------------------------------
-- 3) Incidencias historicas
--    Objetivo por semana: ~2-3 incidencias hace dos anos, subiendo hasta ~4-5 hoy (con ruido).
--    Se RESTAN las que ya existen en esa semana (otros scripts de demo), asi no se
--    forman huecos ni picos raros en los graficos. La semana actual no se toca.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_semanas ON COMMIT DROP AS
SELECT w.w,
       date_trunc('week', now() AT TIME ZONE 'America/Santiago') - w.w * interval '7 days' AS inicio_local,
       round((2.6 + 1.7 * (1 - w.w / 100.0)) * (0.7 + 0.6 * random()))::int AS objetivo
FROM generate_series(1, 99) AS w(w);

CREATE TEMP TABLE tmp_azar ON COMMIT DROP AS
SELECT row_number() OVER () AS i,
       s.w, s.inicio_local,
       random() AS r_dia,   random() AS r_equipo, random() AS r_hora,  random() AS r_hora2,
       random() AS r_min,   random() AS r_tipo,   random() AS r_res,   random() AS r_estado,
       random() AS r_nombre, random() AS r_costo, random() AS r_costo2, random() AS r_desc,
       random() AS r_inicio, random() AS r_tec
FROM (
    SELECT t.*,
           GREATEST(t.objetivo - (
               SELECT COUNT(*) FROM incidencias i
               WHERE (i.fecha_reporte AT TIME ZONE 'America/Santiago') >= t.inicio_local
                 AND (i.fecha_reporte AT TIME ZONE 'America/Santiago') <  t.inicio_local + interval '7 days'
           ), 0)::int AS faltan
    FROM tmp_semanas t
) s
CROSS JOIN LATERAL generate_series(1, s.faltan) AS g(n);

CREATE TEMP TABLE tmp_hist ON COMMIT DROP AS
WITH base AS (
    SELECT a.*,
           p.equipo_id,
           c.codigo, c.costo_min, c.costo_rango, c.horas_min, c.horas_rango, c.descripciones, c.repuestos,
           -- Mas fallas al inicio de la semana (despues del fin de semana): lunes 22 %, martes 18 %...
           CASE WHEN a.r_dia < 0.22 THEN 0 WHEN a.r_dia < 0.40 THEN 1 WHEN a.r_dia < 0.55 THEN 2
                WHEN a.r_dia < 0.70 THEN 3 WHEN a.r_dia < 0.82 THEN 4 WHEN a.r_dia < 0.92 THEN 5 ELSE 6 END AS dia,
           -- Horario punta: tarde (17-20 h) 55 %, manana (7-10 h) 25 %, resto del dia 20 %.
           CASE WHEN a.r_hora < 0.55 THEN 17 + floor(a.r_hora2 * 4)
                WHEN a.r_hora < 0.80 THEN 7 + floor(a.r_hora2 * 4)
                ELSE 11 + floor(a.r_hora2 * 6) END::int AS hora
    FROM tmp_azar a
    JOIN tmp_pool p ON p.k = 1 + floor(a.r_equipo * (SELECT count(*) FROM tmp_pool))::int
    JOIN tmp_cat  c ON c.orden = (SELECT min(orden) FROM tmp_cat WHERE acumulado >= a.r_tipo)
),
con_fecha AS (
    SELECT b.*,
           -- Hora local de Chile convertida a timestamptz (asi el mapa de calor cuadra con lo que ve el usuario).
           ((b.inicio_local + b.dia * interval '1 day')
             + b.hora * interval '1 hour' + floor(b.r_min * 60) * interval '1 minute')
             AT TIME ZONE 'America/Santiago' AS fecha_reporte
    FROM base b
),
con_dias AS (
    SELECT f.*,
           GREATEST(floor(EXTRACT(EPOCH FROM (now() - f.fecha_reporte)) / 86400)::int, 0) AS dias_atras
    FROM con_fecha f
),
con_horas AS (
    SELECT d.*,
           -- Los arreglos mas antiguos tardaban mas: el factor va de 1.0 (hace 2 anos) a 0.55 (reciente).
           (d.horas_min + d.r_res * d.horas_rango) * (0.55 + 0.45 * LEAST(d.dias_atras, 700) / 700.0) AS horas_res
    FROM con_dias d
)
SELECT h.*,
       LEAST(h.fecha_reporte + h.horas_res * interval '1 hour', now() - interval '1 hour') AS fecha_resolucion,
       CASE WHEN h.r_estado < 0.05 THEN 'descartada' ELSE 'resuelta' END AS estado
FROM con_horas h;

INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por,
    prioridad, estado, fecha_reporte, fecha_resolucion, metadata, created_at, updated_at
)
SELECT h.equipo_id,
       tf.id,
       'qr'::origen_incidencia,
       tf.descripcion,
       (ARRAY['Camila Rojas', 'Matías Vega', 'Fernanda Castro', 'Ignacio Soto', 'Juan Pérez', 'María López', 'Carlos Díaz'])[1 + floor(h.r_nombre * 7)::int],
       tf.prioridad_base,
       h.estado::estado_incidencia,
       h.fecha_reporte,
       CASE WHEN h.estado = 'resuelta' THEN h.fecha_resolucion END,
       jsonb_build_object('demo', 'dashboard', 'n', h.i),
       h.fecha_reporte,
       COALESCE(CASE WHEN h.estado = 'resuelta' THEN h.fecha_resolucion END, h.fecha_reporte)
FROM tmp_hist h
JOIN tipos_falla tf ON tf.codigo = h.codigo;

-- ---------------------------------------------------------------------------
-- 4) Mantencion CORRECTIVA de cada incidencia resuelta (con su costo)
-- ---------------------------------------------------------------------------
INSERT INTO mantenimientos (
    equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, created_at, updated_at
)
SELECT i.equipo_id,
       i.id,
       'correctivo',
       (ARRAY['Rodrigo Muñoz', 'Pablo Soto', 'Daniela Vera'])[1 + floor(h.r_tec * 3)::int],
       (ARRAY['TecnoFit Servicios', 'Mantenciones del Sur Ltda.', 'Servicio técnico interno'])[1 + floor(h.r_tec * 3)::int],
       h.descripciones[1 + floor(h.r_desc * 3)::int],
       jsonb_build_array(jsonb_build_object(
           'nombre', h.repuestos[1 + floor(h.r_desc * 3)::int], 'cantidad', 1, 'demo', 'dashboard')),
       -- 7 % se resuelve con personal propio (sin costo); el resto, segun el tipo de falla (con una pequeña alza reciente).
       CASE WHEN h.r_costo < 0.07 THEN 0
            ELSE round((h.costo_min + h.r_costo2 * h.costo_rango) * (1.10 - 0.10 * h.dias_atras / 700.0) / 500) * 500 END,
       LEAST(i.fecha_reporte + (1 + h.r_inicio * 6) * interval '1 hour', i.fecha_resolucion),
       i.fecha_resolucion,
       i.fecha_resolucion,
       i.fecha_resolucion
FROM incidencias i
JOIN tmp_hist h ON h.i = (i.metadata ->> 'n')::int
WHERE i.metadata @> '{"demo": "dashboard"}'::jsonb
  AND i.estado = 'resuelta';

-- 4b) Las incidencias que YA estaban resueltas en la base (otros scripts de demo o
--     cargadas a mano) y no tienen mantencion tambien reciben la suya, con costo.
INSERT INTO mantenimientos (
    equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, created_at, updated_at
)
SELECT x.equipo_id,
       x.id,
       'correctivo',
       (ARRAY['Rodrigo Muñoz', 'Pablo Soto', 'Daniela Vera'])[1 + floor(x.r_tec * 3)::int],
       (ARRAY['TecnoFit Servicios', 'Mantenciones del Sur Ltda.', 'Servicio técnico interno'])[1 + floor(x.r_tec * 3)::int],
       c.descripciones[1 + floor(x.r_desc * 3)::int],
       jsonb_build_array(jsonb_build_object(
           'nombre', c.repuestos[1 + floor(x.r_desc * 3)::int], 'cantidad', 1, 'demo', 'dashboard')),
       round((c.costo_min + x.r_costo * c.costo_rango) / 500) * 500,
       LEAST(x.fecha_reporte + (1 + x.r_inicio * 6) * interval '1 hour', x.fecha_resolucion),
       x.fecha_resolucion,
       x.fecha_resolucion,
       x.fecha_resolucion
FROM (
    SELECT i.id, i.equipo_id, i.fecha_reporte, i.fecha_resolucion, tf.codigo,
           random() AS r_tec, random() AS r_desc, random() AS r_costo, random() AS r_inicio
    FROM incidencias i
    JOIN tipos_falla tf ON tf.id = i.tipo_falla_id
    WHERE i.estado = 'resuelta'
      AND i.fecha_resolucion IS NOT NULL
      AND NOT (i.metadata @> '{"demo": "dashboard"}'::jsonb)
      AND NOT EXISTS (SELECT 1 FROM mantenimientos m WHERE m.incidencia_id = i.id)
) x
JOIN tmp_cat c ON c.codigo = CASE WHEN x.codigo = 'MOVIMIENTO_ANOMALO' THEN 'OTRO' ELSE x.codigo END;

-- ---------------------------------------------------------------------------
-- 5) Mantenciones PREVENTIVAS programadas
--    Maquinas sanas: cardio y fuerza ~cada 3 meses; funcional y peso libre ~cada 6
--    (durante los ultimos ~2 anos).
--    Cada maquina tiene su propio desfase (0-59 dias) para que no coincidan todas el mismo mes.
--    Las problematicas casi no tienen (por eso fallan mas).
-- ---------------------------------------------------------------------------
INSERT INTO mantenimientos (
    equipo_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, proximo_mantenimiento, created_at, updated_at
)
SELECT q.equipo_id,
       'preventivo',
       (ARRAY['Rodrigo Muñoz', 'Pablo Soto', 'Daniela Vera'])[1 + floor(q.r_tec * 3)::int],
       (ARRAY['TecnoFit Servicios', 'Mantenciones del Sur Ltda.', 'Servicio técnico interno'])[1 + floor(q.r_tec * 3)::int],
       'Mantención preventiva programada: limpieza, lubricación y revisión de componentes',
       '[{"nombre": "Kit de lubricación y limpieza", "cantidad": 1, "demo": "dashboard"}]'::jsonb,
       round((CASE q.categoria WHEN 'cardio' THEN 35000 + q.r_costo * 45000
                               WHEN 'fuerza' THEN 25000 + q.r_costo * 40000
                               ELSE 8000 + q.r_costo * 17000 END) / 500) * 500,
       q.inicio,
       q.inicio + (1.5 + q.r_costo * 1.5) * interval '1 hour',
       (q.inicio + (CASE WHEN q.categoria IN ('cardio', 'fuerza') THEN 90 ELSE 180 END) * interval '1 day')::date,
       q.inicio + interval '3 hour',
       q.inicio + interval '3 hour'
FROM (
    SELECT e.id AS equipo_id, e.categoria, random() AS r_tec, random() AS r_costo, random() AS r_salto,
           ((date_trunc('day', now() AT TIME ZONE 'America/Santiago')
               - (o.dias + (e.id * 17) % 60 - 8 + floor(random() * 17)) * interval '1 day'
               + interval '9 hour' + floor(random() * 120) * interval '1 minute')
             AT TIME ZONE 'America/Santiago') AS inicio
    FROM equipos e
    CROSS JOIN LATERAL unnest(
        CASE WHEN e.codigo_activo IN ('EQ-0002', 'EQ-0003', 'EQ-0007', 'EQ-0014', 'EQ-0017') THEN ARRAY[650, 290]
             WHEN e.categoria IN ('cardio', 'fuerza')                                         THEN ARRAY[660, 570, 480, 390, 300, 210, 120, 35]
             ELSE ARRAY[640, 460, 280, 100] END
    ) AS o(dias)
    WHERE e.codigo_activo LIKE 'EQ-%' AND e.estado <> 'retirado'
) q
WHERE q.r_salto >= 0.12;   -- ~12 % de las mantenciones programadas se saltaron

-- ---------------------------------------------------------------------------
-- 6) Inspecciones de las maquinas de fuerza (sin costo: personal propio)
-- ---------------------------------------------------------------------------
INSERT INTO mantenimientos (
    equipo_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, created_at, updated_at
)
SELECT e.id,
       'inspeccion',
       'Pablo Soto',
       'Servicio técnico interno',
       'Inspección de seguridad: estado de cables, pernos y puntos de apoyo',
       '[{"nombre": "Revisión visual", "cantidad": 1, "demo": "dashboard"}]'::jsonb,
       0,
       t.inicio,
       t.inicio + interval '45 minute',
       t.inicio,
       t.inicio
FROM equipos e
CROSS JOIN LATERAL (
    SELECT ((date_trunc('day', now() AT TIME ZONE 'America/Santiago')
              - (k.base + (e.id * 7) % 20 + floor(random() * 15)) * interval '1 day' + interval '10 hour')
            AT TIME ZONE 'America/Santiago') AS inicio
    FROM unnest(ARRAY[60, 240, 420, 600]) AS k(base)
) t
WHERE e.codigo_activo LIKE 'EQ-%' AND e.categoria = 'fuerza' AND e.estado <> 'retirado';

-- ---------------------------------------------------------------------------
-- 7) Situaciones "de hoy": para que se vean los avisos de Atencion recomendada
-- ---------------------------------------------------------------------------
-- 7a) Dos incidencias graves sin atender hace varios dias
INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por,
    prioridad, estado, fecha_reporte, metadata, created_at, updated_at
)
SELECT e.id, tf.id, 'qr'::origen_incidencia, v.descripcion, v.reportado_por,
       v.prioridad::prioridad_incidencia, 'pendiente'::estado_incidencia,
       now() - (v.dias_atras || ' days')::interval,
       '{"demo": "dashboard"}'::jsonb,
       now() - (v.dias_atras || ' days')::interval,
       now() - (v.dias_atras || ' days')::interval
FROM (
    VALUES
        ('EQ-0008', 'ROTA',        'Se cortó el cable de la polea; la máquina quedó inutilizable.', 'Ignacio Soto', 'urgente', 5),
        ('EQ-0021', 'NO_ENCIENDE', 'La jaula no responde al panel de control desde el fin de semana.', 'Camila Rojas', 'alta',    4)
) AS v(codigo_activo, tipo_falla_codigo, descripcion, reportado_por, prioridad, dias_atras)
JOIN equipos e ON e.codigo_activo = v.codigo_activo
JOIN tipos_falla tf ON tf.codigo = v.tipo_falla_codigo;

-- 7b) Mantencion abierta (en taller) para cada maquina que esta "en mantenimiento"
INSERT INTO mantenimientos (
    equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
    fecha_inicio, created_at, updated_at
)
SELECT e.id,
       (SELECT i.id FROM incidencias i
         WHERE i.equipo_id = e.id AND i.estado IN ('pendiente', 'en_proceso')
         ORDER BY i.fecha_reporte LIMIT 1),
       'correctivo',
       'Rodrigo Muñoz',
       'TecnoFit Servicios',
       'Equipo en taller: diagnóstico y reparación en curso',
       '[{"nombre": "Diagnóstico", "cantidad": 1, "demo": "dashboard"}]'::jsonb,
       now() - interval '2 day',
       now() - interval '2 day',
       now() - interval '2 day'
FROM equipos e
WHERE e.estado = 'en_mantenimiento' AND e.codigo_activo LIKE 'EQ-%';

COMMIT;

-- ---------------------------------------------------------------------------
-- Resumen (se imprime al ejecutar): incidencias y gasto por mes
-- ---------------------------------------------------------------------------
SELECT to_char(date_trunc('month', i.fecha_reporte AT TIME ZONE 'America/Santiago'), 'YYYY-MM') AS mes,
       COUNT(*) AS incidencias,
       COUNT(*) FILTER (WHERE i.estado = 'resuelta') AS resueltas,
       ROUND(AVG(EXTRACT(EPOCH FROM (i.fecha_resolucion - i.fecha_reporte)) / 3600) FILTER (WHERE i.estado = 'resuelta')) AS horas_promedio_resolucion
FROM incidencias i
GROUP BY 1
ORDER BY 1;

SELECT to_char(date_trunc('month', COALESCE(m.fecha_fin, m.fecha_inicio) AT TIME ZONE 'America/Santiago'), 'YYYY-MM') AS mes,
       COUNT(*) AS mantenciones,
       COUNT(*) FILTER (WHERE m.tipo = 'preventivo') AS preventivas,
       COALESCE(SUM(m.costo_total) FILTER (WHERE m.tipo = 'correctivo'), 0) AS gasto_correctivo,
       COALESCE(SUM(m.costo_total) FILTER (WHERE m.tipo = 'preventivo'), 0) AS gasto_preventivo
FROM mantenimientos m
GROUP BY 1
ORDER BY 1;
