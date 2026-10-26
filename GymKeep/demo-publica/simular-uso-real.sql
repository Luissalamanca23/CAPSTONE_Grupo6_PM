-- ============================================================================
-- simular-uso-real.sql
--
-- Deja la base lista para una demostracion que se vea como un gimnasio real:
--
--   1. BORRA TODAS las sesiones de uso (sesiones_uso) y genera sesiones nuevas, una por cada
--      vez que alguien usa una maquina (no consolidadas por franja), hasta el minuto actual.
--      * Cuanto se usa cada maquina sale del historial que ya haya en la base (si no hay,
--        de un valor tipico por categoria); las mas populares tienen mas sesiones.
--      * Horario real de un gimnasio: abre a las 06:00 y cierra a las 23:00, con punta de
--        7-9 h y de 17-20 h, y valle a media tarde. Una maquina nunca tiene dos sesiones
--        a la vez.
--      * Mas gente lunes y martes, menos en fin de semana; menos en enero-febrero.
--      * Duracion segun el tipo: cardio ~25 min, maquinas de placas ~9 min, etc.
--      * ~1,5 % de sesiones "descartadas" (detecciones cortas que no fueron uso real).
--   2. Agrega PROBLEMAS recientes (incidencias reportadas por QR): una cinta fuera de servicio,
--      una bicicleta en reparacion, un cable gastado, un banco con tapiz roto, algunas ya
--      resueltas con su mantencion. Las maquinas paradas dejan de tener sesiones desde que
--      se reporto la falla.
--
-- Se puede correr cuantas veces se quiera: cada corrida vuelve a generar todo hasta "ahora"
-- (lo marcado "simulacion_real" se borra y se rehace). Lo demas no se toca.
--
-- A mano (PowerShell, desde GymKeep):
--   docker compose -f demo-publica\docker-compose.yml cp demo-publica\simular-uso-real.sql db:/tmp/simular.sql
--   docker compose -f demo-publica\docker-compose.yml exec -T db psql -U gymkeep -d gymkeep -f /tmp/simular.sql
-- ============================================================================
\set ON_ERROR_STOP on
\encoding UTF8

-- ---- Ajustes ---------------------------------------------------------------
-- Dias de historia que se generan hacia atras (730 = 2 anos).
\set dias 730
-- ----------------------------------------------------------------------------

BEGIN;
SELECT setseed(0.42);

-- Referencia de tiempo (hora de Chile).
CREATE TEMP TABLE tmp_p ON COMMIT DROP AS
SELECT (now() AT TIME ZONE 'America/Santiago')::date AS hoy,
       ((now() AT TIME ZONE 'America/Santiago')::date - (:dias - 1))::date AS desde;

-- ---------------------------------------------------------------------------
-- 0) Limpiar lo que dejo una corrida anterior de este script
-- ---------------------------------------------------------------------------
UPDATE equipos SET estado = 'operativo'
WHERE estado IN ('en_mantenimiento', 'fuera_de_servicio')
  AND id IN (SELECT equipo_id FROM incidencias WHERE metadata ->> 'demo' = 'simulacion_real');
DELETE FROM mantenimientos WHERE repuestos @> '[{"demo": "simulacion_real"}]'::jsonb;
DELETE FROM incidencias    WHERE metadata ->> 'demo' = 'simulacion_real';

-- ---------------------------------------------------------------------------
-- 1) Perfil de uso de cada maquina (se calcula ANTES de borrar las sesiones)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_cat ON COMMIT DROP AS
SELECT e.id AS equipo_id, e.estado AS estado_antes,
       CASE
           WHEN e.categoria IN ('cardio', 'placas', 'discos', 'peso_libre', 'bancos_racks', 'funcional') THEN e.categoria
           WHEN n ~ '(cinta|trotadora|caminadora|treadmill|bicicleta|bike|spinning|eliptic|remadora|remo|escalador|stairmaster|skierg|assault)' THEN 'cardio'
           WHEN n ~ '(banda|elastic|battle|cuerda|plyo|cajon|trx|bosu|foam|rodillo)' THEN 'funcional'
           WHEN n ~ '(banco|rack|jaula|smith|multipower|power tower|torre de|predicador|scott)' THEN 'bancos_racks'
           WHEN n ~ '(hammer|hack|prensa|hip.?thrust|pendulum)' THEN 'discos'
           WHEN n ~ '(mancuerna|barra|disco|kettlebell|pesa rusa|balon medicinal)' THEN 'peso_libre'
           ELSE 'placas'
       END AS cat
FROM (SELECT id, estado, categoria, translate(lower(nombre), 'áéíóúüñ', 'aeiouun') AS n FROM equipos) e
WHERE e.estado <> 'retirado';

-- El perfil se guarda la primera vez (con las sesiones que traia la base) y se reutiliza despues,
-- para que correr el script otra vez no vaya cambiando el nivel de uso de cada maquina.
CREATE TABLE IF NOT EXISTS demo_perfil_uso (equipo_id bigint PRIMARY KEY, horas_dia numeric NOT NULL);
INSERT INTO demo_perfil_uso (equipo_id, horas_dia)
SELECT equipo_id,
       SUM(duracion_segundos) / 3600.0 / GREATEST(1, COUNT(DISTINCT (fecha_inicio AT TIME ZONE 'America/Santiago')::date))
FROM sesiones_uso
WHERE estado = 'cerrada' AND fecha_inicio >= now() - interval '365 days'
  AND COALESCE(metadata ->> 'demo', '') <> 'simulacion_real'
GROUP BY equipo_id
HAVING SUM(duracion_segundos) > 0
ON CONFLICT (equipo_id) DO NOTHING;

CREATE TEMP TABLE tmp_perfil ON COMMIT DROP AS
SELECT c.equipo_id, c.cat, c.estado_antes,
       -- Horas de uso por dia con actividad: lo que ya habia en la base, o un valor tipico.
       LEAST(6.0, GREATEST(0.25, COALESCE(h.horas_dia,
           CASE c.cat WHEN 'cardio' THEN 2.6 WHEN 'placas' THEN 1.7 WHEN 'discos' THEN 1.4
                      WHEN 'peso_libre' THEN 3.2 WHEN 'bancos_racks' THEN 3.0 ELSE 1.1 END
       )))::numeric AS horas,
       -- Duracion media de una sesion, en segundos.
       CASE c.cat WHEN 'cardio' THEN 1500 WHEN 'placas' THEN 540 WHEN 'discos' THEN 600
                  WHEN 'peso_libre' THEN 720 WHEN 'bancos_racks' THEN 840 ELSE 540 END AS dur_s,
       -- Camara que la ve: la de su zona; si no, la primera que exista.
       COALESCE((SELECT ca.id FROM camaras ca JOIN equipos e ON e.zona_id = ca.zona_id
                  WHERE e.id = c.equipo_id ORDER BY ca.id LIMIT 1),
                (SELECT MIN(id) FROM camaras)) AS camara_id
FROM tmp_cat c
LEFT JOIN demo_perfil_uso h ON h.equipo_id = c.equipo_id;

-- Todas las sesiones anteriores (de la IA, manuales o de otra demo) se eliminan.
DELETE FROM sesiones_uso;

-- ---------------------------------------------------------------------------
-- 2) Problemas recientes (incidencias por QR) y maquinas paradas
-- ---------------------------------------------------------------------------
-- Cada fila: que maquina buscar (por nombre), la falla y su estado. "efecto":
--   fuera  = queda fuera de servicio    taller = queda en mantenimiento (con tecnico)
--   parada = estuvo parada y ya volvio  sigue  = se sigue usando
CREATE TEMP TABLE tmp_esc (
    ord int, rx text, falla text, descripcion text, reportado_por text, prioridad text, estado text,
    horas_atras numeric, horas_resolucion numeric, efecto text, costo numeric, trabajo text, repuesto text
) ON COMMIT DROP;
INSERT INTO tmp_esc VALUES
 (1, '(cinta|trotadora|caminadora)', 'ROTA',           'La banda se traba y la cinta se detiene sola a mitad de la carrera.', 'Camila Rojas',    'urgente', 'pendiente',   5,    NULL, 'fuera',  NULL,   NULL, NULL),
 (2, '(bicicleta|bike|spinning)',    'SONIDO_EXTRANO', 'Ruido metalico al pedalear fuerte, parece el pedal flojo.',            'Matias Vega',     'media',   'en_proceso', 26,    NULL, 'taller', NULL,   'Revision de pedales y rodamiento del eje', 'Rodamiento de pedal'),
 (3, '(polea|jalon|cruce|cable|multiestacion|remo)', 'DESGASTE', 'El cable de la polea tiene hilos sueltos, se nota gastado.', 'Ignacio Soto',    'alta',    'pendiente',   52,   NULL, 'sigue',  NULL,   NULL, NULL),
 (4, '(banco|press)',                'OTRO',           'El tapiz del banco esta roto y se ve la espuma.',                      'Fernanda Castro', 'baja',    'pendiente',   71,   NULL, 'sigue',  NULL,   NULL, NULL),
 (5, '(cinta|trotadora|caminadora)', 'NO_ENCIENDE',    'La cinta no enciende, la pantalla queda en negro.',                    'Daniela Pino',    'urgente', 'resuelta',    96,   20,   'parada', 85000,  'Cambio de fuente de poder y revision electrica', 'Fuente de poder'),
 (6, '(eliptic|escalador|remadora)', 'SONIDO_EXTRANO', 'Se escucha un golpe seco en cada pasada.',                              'Pablo Araya',     'media',   'resuelta',    190,  30,   'parada', 42000,  'Lubricacion y ajuste de la biela', 'Kit de lubricacion'),
 (7, '(mancuerna|barra|disco)',      'DESGASTE',       'El agarre de una mancuerna se esta soltando.',                         'Matias Vega',     'baja',    'pendiente',   6,    NULL, 'sigue',  NULL,   NULL, NULL),
 (8, '(prensa|hack|hammer|smith)',   'ROTA',           'El seguro de la carga no traba bien.',                                 'Camila Rojas',    'alta',    'descartada',  120,  NULL, 'sigue',  NULL,   NULL, NULL);

CREATE TEMP TABLE tmp_indisp (equipo_id bigint, desde timestamptz, hasta timestamptz) ON COMMIT DROP;

DO $$
DECLARE
    r record;
    eid bigint;
    iid bigint;
    reporte timestamptz;
    resolucion timestamptz;
    usados bigint[] := '{}';
BEGIN
    FOR r IN SELECT * FROM tmp_esc ORDER BY ord LOOP
        -- Primero una maquina operativa cuyo nombre calce; si no hay, cualquier operativa libre.
        SELECT e.id INTO eid FROM equipos e
        WHERE e.estado = 'operativo' AND NOT (e.id = ANY (usados))
          AND translate(lower(e.nombre), 'áéíóúüñ', 'aeiouun') ~ r.rx
        ORDER BY e.id LIMIT 1;
        IF eid IS NULL THEN
            SELECT e.id INTO eid FROM equipos e
            WHERE e.estado = 'operativo' AND NOT (e.id = ANY (usados))
            ORDER BY (e.id * 7919) % 101 LIMIT 1;
        END IF;
        CONTINUE WHEN eid IS NULL;
        usados := usados || eid;

        reporte := now() - r.horas_atras * interval '1 hour';
        resolucion := CASE WHEN r.horas_resolucion IS NOT NULL THEN reporte + r.horas_resolucion * interval '1 hour' END;

        INSERT INTO incidencias (equipo_id, tipo_falla_id, qr_id, origen, descripcion, reportado_por,
                                 prioridad, estado, fecha_reporte, fecha_resolucion, metadata, created_at, updated_at)
        SELECT eid, tf.id,
               (SELECT q.id FROM qr_equipos q WHERE q.equipo_id = eid AND q.activo ORDER BY q.id DESC LIMIT 1),
               'qr'::origen_incidencia, r.descripcion, r.reportado_por,
               r.prioridad::prioridad_incidencia, r.estado::estado_incidencia, reporte, resolucion,
               '{"demo": "simulacion_real"}'::jsonb, reporte, COALESCE(resolucion, reporte)
        FROM tipos_falla tf WHERE tf.codigo = r.falla
        RETURNING id INTO iid;

        IF r.efecto = 'fuera' THEN
            UPDATE equipos SET estado = 'fuera_de_servicio' WHERE id = eid;
            INSERT INTO tmp_indisp VALUES (eid, reporte, 'infinity');
        ELSIF r.efecto = 'taller' THEN
            UPDATE equipos SET estado = 'en_mantenimiento' WHERE id = eid;
            INSERT INTO tmp_indisp VALUES (eid, reporte + interval '1 hour', 'infinity');
            INSERT INTO mantenimientos (equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
                                        costo_total, fecha_inicio, fecha_fin, created_at, updated_at)
            VALUES (eid, iid, 'correctivo', 'Rodrigo Muñoz', 'TecnoFit Servicios', r.trabajo,
                    jsonb_build_array(jsonb_build_object('nombre', r.repuesto, 'cantidad', 1, 'demo', 'simulacion_real')),
                    NULL, reporte + interval '3 hour', NULL, reporte + interval '3 hour', reporte + interval '3 hour');
        ELSIF r.efecto = 'parada' THEN
            INSERT INTO tmp_indisp VALUES (eid, reporte, resolucion);
            INSERT INTO mantenimientos (equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
                                        costo_total, fecha_inicio, fecha_fin, created_at, updated_at)
            VALUES (eid, iid, 'correctivo', 'Pablo Soto', 'Mantenciones del Sur Ltda.', r.trabajo,
                    jsonb_build_array(jsonb_build_object('nombre', r.repuesto, 'cantidad', 1, 'demo', 'simulacion_real')),
                    r.costo, reporte + interval '2 hour', resolucion, resolucion, resolucion);
        END IF;
    END LOOP;
END $$;

-- Maquinas que ya estaban paradas antes (en taller / fuera de servicio): sin sesiones la ultima semana.
INSERT INTO tmp_indisp
SELECT equipo_id, now() - interval '7 days', 'infinity'
FROM tmp_perfil WHERE estado_antes IN ('en_mantenimiento', 'fuera_de_servicio');

-- ---------------------------------------------------------------------------
-- 3) Sesiones de uso
-- ---------------------------------------------------------------------------
-- Curva de afluencia por hora (peso relativo): punta de manana y de tarde-noche.
CREATE TEMP TABLE tmp_horas (h int, w numeric) ON COMMIT DROP;
INSERT INTO tmp_horas VALUES
 (6, 3), (7, 7), (8, 8), (9, 6), (10, 4), (11, 4), (12, 6), (13, 6), (14, 4),
 (15, 3), (16, 5), (17, 9), (18, 12), (19, 12), (20, 9), (21, 5), (22, 1);

-- Un factor aleatorio por maquina y dia (hay dias mas movidos que otros).
CREATE TEMP TABLE tmp_eqdia ON COMMIT DROP AS
SELECT f.equipo_id, f.dia, f.horas, f.dur_s, f.camara_id,
       f.horas * 3600.0 / f.dur_s                      -- sesiones al dia, a un dia normal
         * f.factor_dia
         * (0.60 + 0.80 * random())                      -- variacion diaria
         / (SELECT SUM(w) FROM tmp_horas) AS por_peso   -- sesiones por unidad de peso de hora
FROM (
    SELECT p.equipo_id, p.horas, p.dur_s, p.camara_id, d.dia,
           -- Dia de la semana: mas lunes/martes, menos fin de semana.
           (CASE extract(isodow FROM d.dia)::int WHEN 1 THEN 1.15 WHEN 2 THEN 1.12 WHEN 3 THEN 1.0 WHEN 4 THEN 1.0
                                                 WHEN 5 THEN 0.88 WHEN 6 THEN 0.62 ELSE 0.45 END)
           -- Estacion: verano flojo, marzo-abril y septiembre-noviembre fuertes.
           * (CASE WHEN extract(month FROM d.dia) IN (1, 2) THEN 0.80
                   WHEN extract(month FROM d.dia) IN (3, 4, 9, 10, 11) THEN 1.12 ELSE 1.0 END)
           -- Tendencia: el gimnasio fue creciendo (hace 2 anos tenia ~15 % menos gente que hoy).
           * (0.85 + 0.15 * (d.dia - (SELECT desde FROM tmp_p))::numeric / :dias) AS factor_dia
    FROM tmp_perfil p
    CROSS JOIN (SELECT generate_series((SELECT desde FROM tmp_p), (SELECT hoy FROM tmp_p), interval '1 day')::date AS dia) d
) f;

-- Cuantas sesiones empiezan en cada hora (con un tope: caben en la hora sin pisarse).
CREATE TEMP TABLE tmp_franja ON COMMIT DROP AS
SELECT x.*, LEAST(x.cap, GREATEST(0, round(x.esperadas + random() - 0.5)::int)) AS n
FROM (
    SELECT e.equipo_id, e.dia, h.h, e.dur_s, e.camara_id,
           e.por_peso * h.w AS esperadas,
           floor(3600.0 / (e.dur_s * 1.3))::int AS cap
    FROM tmp_eqdia e CROSS JOIN tmp_horas h
) x;
DELETE FROM tmp_franja WHERE n = 0;

-- Dentro de cada hora, las n sesiones se reparten en n tramos seguidos (nunca se pisan).
INSERT INTO sesiones_uso (
    equipo_id, camara_id, origen, fecha_inicio, fecha_fin, duracion_segundos, confianza_promedio,
    cantidad_eventos, estado, metadata, created_at, updated_at
)
SELECT s.equipo_id, s.camara_id, 'ia'::origen_uso, s.ini,
       s.ini + s.dur * interval '1 second', s.dur,
       s.conf, GREATEST(2, (s.dur / 20)::int),
       s.estado, '{"demo": "simulacion_real"}'::jsonb, s.ini, s.ini
FROM (
    SELECT t.equipo_id, t.camara_id,
           ((t.dia + make_interval(hours => t.h)) AT TIME ZONE 'America/Santiago') + tramo.ini_s * interval '1 second' AS ini,
           CASE WHEN tramo.descartada THEN 5 + floor(random() * 20)::int ELSE tramo.dur END AS dur,
           CASE WHEN tramo.descartada THEN 'descartada' ELSE 'cerrada' END AS estado,
           round((0.72 + 0.25 * random())::numeric, 4) AS conf
    FROM tmp_franja t
    CROSS JOIN LATERAL (
        SELECT gs.k,
               floor((gs.k - 1) * 3600.0 / t.n + random() * 0.35 * 3600.0 / t.n)::int AS ini_s,
               GREATEST(60, LEAST(
                   floor(t.dur_s * (0.55 + 0.90 * random()))::int,
                   floor(3600.0 / t.n * 0.62)::int)) AS dur,
               random() < 0.015 AS descartada
        FROM generate_series(1, t.n) AS gs(k)
    ) tramo
) s
WHERE s.ini + s.dur * interval '1 second' < now() - interval '1 minute'
  AND NOT EXISTS (
      SELECT 1 FROM tmp_indisp i
      WHERE i.equipo_id = s.equipo_id AND s.ini >= i.desde AND s.ini < i.hasta
  );

COMMIT;

ANALYZE sesiones_uso;

-- ---------------------------------------------------------------------------
-- Resumen (se imprime al ejecutar)
-- ---------------------------------------------------------------------------
\echo
\echo '== Sesiones de uso generadas =='
SELECT COUNT(*) AS sesiones,
       COUNT(*) FILTER (WHERE estado = 'descartada') AS descartadas,
       ROUND(SUM(duracion_segundos) FILTER (WHERE estado = 'cerrada') / 3600.0) AS horas_de_uso,
       MIN(fecha_inicio)::date AS desde, MAX(fecha_inicio) AS ultima
FROM sesiones_uso;

\echo
\echo '== Problemas recientes =='
SELECT e.codigo_activo, e.nombre, e.estado AS estado_maquina, tf.nombre AS falla, i.prioridad, i.estado AS estado_reporte
FROM incidencias i
JOIN equipos e ON e.id = i.equipo_id
JOIN tipos_falla tf ON tf.id = i.tipo_falla_id
WHERE i.metadata ->> 'demo' = 'simulacion_real'
ORDER BY i.fecha_reporte DESC;
