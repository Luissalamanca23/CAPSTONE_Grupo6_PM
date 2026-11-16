-- ============================================================================
-- historial_caf_duoc.sql
--
-- Deja la base de datos lista para el CAF (Centro de Acondicionamiento Físico) de Duoc UC,
-- sede Puerto Montt, que abrió sus puertas el 13 de agosto de 2024. Sirve cuando ya
-- ingresaste (o editaste) las máquinas reales y quieres que el sistema muestre un historial
-- coherente con la realidad del CAF:
--
--   1. LIMPIA todas las incidencias, mantenciones, sesiones de uso y resúmenes de eventos de
--      IA que había (datos de pruebas y demos anteriores) y deja todas las máquinas (menos las
--      retiradas) en estado "operativo". Después carga el historial de abajo.
--   2. FECHAS de las máquinas: se instalan justo antes de la apertura (2 a 9 días antes) y se
--      compraron entre 10 y 40 días antes de instalarse. También recalcula su vida útil.
--   3. USO: una fila por máquina, por día y por franja, desde el 13 de agosto de 2024 hasta
--      ayer. Respeta el horario del CAF:
--          lunes a sábado, de 8:30 a 18:30 (nunca domingo ni feriados),
--          franja de mañana 8:30-13:30 y franja de tarde 13:30-18:30.
--      Las máquinas de fuerza (placas, discos, bancos y racks) y las caminadoras se usan más
--      que el resto; las bicicletas, elípticas y el peso libre, algo menos; lo funcional, poco.
--      Hay más uso lunes a jueves, menos el viernes y mucho menos el sábado; más uso en
--      periodo de clases (marzo a junio y agosto a noviembre), menos en julio y en verano
--      (diciembre a febrero); y durante las primeras semanas el uso crece de a poco.
--   4. MANTENCIONES de rutina:
--        - INSPECCIÓN mensual del personal del CAF (primer lunes de cada mes, costo $0).
--        - MANTENCIÓN TRIMESTRAL del proveedor (cada 90 días) a todas las máquinas, con un
--          valor de $45.000 por visita (se registra una vez por visita, en la primera máquina).
--   5. INCIDENCIAS (todas ya SOLUCIONADAS): el PRIMER AÑO (hasta el 13 de agosto de 2025)
--      sin ninguna falla. Desde el segundo año aparecen pocas y pequeñas, sobre todo en la
--      máquina con poleas (desgaste de poleas, se cortó la polea, chirrido) y en las
--      caminadoras (no prendía, banda desalineada, desgaste), más un pedal suelto en una
--      bicicleta y el tapiz gastado de un banco. Cada una tiene su mantención correctiva y,
--      mientras una máquina estuvo parada, no tiene uso. Si no hay una máquina de ese tipo
--      (por nombre), esa incidencia simplemente se omite.
--
-- Las cifras de uso son de DEMOSTRACIÓN: se generan con una receta, no vienen de cámaras.
-- Es seguro correrlo más de una vez: siempre borra y vuelve a generar lo mismo.
--
-- ⚠ IRREVERSIBLE: borra TODAS las incidencias, mantenciones y sesiones de uso. Antes de
--    correrlo haz un respaldo (ver más abajo). Las fechas originales de cada máquina quedan
--    guardadas en la tabla respaldo_fechas_equipos.
--
-- Cómo ejecutarlo (con Docker levantado), desde la carpeta GymKeep, en PowerShell:
--
--   1) Respaldo (recomendado):
--        docker compose exec -T db pg_dump -U gymkeep gymkeep > respaldo_antes_del_caf.sql
--
--   2) Copiar el archivo dentro del contenedor (así las tildes llegan bien) y ejecutarlo:
--        docker compose cp postgres\historial_caf_duoc.sql db:/tmp/historial_caf_duoc.sql
--        docker compose exec db psql -U gymkeep -d gymkeep -f /tmp/historial_caf_duoc.sql
--
-- Tarda unos segundos. Si cambias los ajustes de abajo, vuelve a ejecutarlo.
-- ============================================================================

\set ON_ERROR_STOP on
\encoding UTF8

-- ---- Ajustes (puedes cambiarlos) -------------------------------------------
-- Día de apertura del CAF.
\set apertura '2024-08-13'
-- Cada cuántos días hace la mantención el proveedor (90 = trimestral).
\set cada_dias 90
-- Valor de cada mantención trimestral del proveedor, en CLP (se registra una vez por visita).
\set cuota_visita 45000
-- ----------------------------------------------------------------------------

BEGIN;

SELECT setseed(0.42);

-- ---------------------------------------------------------------------------
-- 0) Limpiar incidencias, mantenciones y uso
-- ---------------------------------------------------------------------------
DELETE FROM eventos_ia_resumen;
DELETE FROM sesiones_uso;
DELETE FROM mantenimientos;
DELETE FROM incidencias;

UPDATE equipos SET estado = 'operativo' WHERE estado <> 'retirado';

-- Respaldo (solo de las máquinas que aún no estaban respaldadas) de lo que se modifica.
CREATE TABLE IF NOT EXISTS respaldo_fechas_equipos AS
SELECT id, fecha_adquisicion, fecha_instalacion, vida_util_meses, now() AS respaldado_en FROM equipos;

INSERT INTO respaldo_fechas_equipos
SELECT id, fecha_adquisicion, fecha_instalacion, vida_util_meses, now()
FROM equipos WHERE id NOT IN (SELECT id FROM respaldo_fechas_equipos);

-- Fechas de referencia (hora de Chile).
CREATE TEMP TABLE tmp_p ON COMMIT DROP AS
SELECT (now() AT TIME ZONE 'America/Santiago')::date AS hoy,
       :'apertura'::date AS apertura;

-- ---------------------------------------------------------------------------
-- 1) Perfil de cada máquina: tipo, uso diario, fechas y vida útil
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_eq0 ON COMMIT DROP AS
SELECT s.*,
       -- Tipo de equipo (las 6 categorías del gimnasio). Si una máquina aún trae una categoría
       -- antigua ("fuerza", "otro", vacía), se deduce del nombre.
       CASE
           WHEN s.categoria IN ('cardio', 'placas', 'discos', 'peso_libre', 'bancos_racks', 'funcional') THEN s.categoria
           WHEN s.n ~ '(cinta|trotadora|caminadora|treadmill|bicicleta|bike|spinning|eliptic|remadora|maquina de remo|escalador|stairmaster|skierg|ski erg|assault)' THEN 'cardio'
           WHEN s.n ~ '(banda|elastic|battle|cuerda|plyo|cajon|trx|bosu|foam|rodillo)' THEN 'funcional'
           WHEN s.n ~ '(banco|rack|jaula|smith|multipower|power tower|torre de|predicador|scott)' THEN 'bancos_racks'
           WHEN s.n ~ '(hammer|hack|prensa.*45|hip.?thrust|pendulum)' THEN 'discos'
           WHEN s.n ~ '(mancuerna|barra|disco|kettlebell|pesa rusa|balon medicinal)' THEN 'peso_libre'
           ELSE 'placas'
       END AS cat
FROM (
    SELECT e.id, e.codigo_activo, e.nombre, e.categoria,
           translate(lower(e.nombre), 'áéíóúüñ', 'aeiouun') AS n,
           random() AS r_uso, random() AS r_adq, random() AS r_ins
    FROM equipos e
    WHERE e.estado <> 'retirado'
) s;

CREATE TEMP TABLE tmp_eq1 ON COMMIT DROP AS
SELECT q.*,
       CASE
           WHEN q.n ~ '(cinta|trotadora|caminadora|treadmill)' THEN 'caminadora'
           WHEN q.n ~ '(bicicleta|bike|spinning)'              THEN 'bicicleta'
           ELSE 'otro'
       END AS grp
FROM tmp_eq0 q;

CREATE TEMP TABLE tmp_eq2 ON COMMIT DROP AS
SELECT q.*,
       -- Horas de uso en un día hábil típico (de 10 h de apertura). En el CAF se ocupan más las
       -- máquinas de fuerza y las caminadoras.
       CASE
           WHEN q.grp = 'caminadora'                                                        THEN 5.2
           WHEN q.grp = 'bicicleta'                                                         THEN 3.0
           WHEN q.n ~ 'eliptic'                                                             THEN 3.0
           WHEN q.n ~ '(skierg|ski erg|remadora|rower|escalador|stairmaster|maquina de remo|assault)' THEN 1.6
           WHEN q.cat = 'cardio'                                                            THEN 2.2
           WHEN q.n ~ 'soporte (para|de) '                                                  THEN 0.3
           WHEN q.n ~ '(mancuernas|dumbbells|juego de|set de)'                              THEN 5.0
           WHEN q.n ~ '(mancuerna|dumbbell)'                                                THEN 1.4
           WHEN q.n ~ 'banco' AND q.n ~ '(plano|inclin|declin|press)'                       THEN 4.8
           WHEN q.n ~ '(smith|multipower)'                                                  THEN 4.2
           WHEN q.n ~ '(jaula|rack|power)'                                                  THEN 4.6
           WHEN q.n ~ 'prensa'                                                              THEN 4.6
           WHEN q.n ~ '(polea|jalon|pulldown|cruce|cable|crossover|multiestacion|remo sentado)' THEN 4.4
           WHEN q.n ~ '(extension|cuadriceps|curl|femoral|isquio)'                          THEN 4.0
           WHEN q.n ~ '(pec ?deck|mariposa|contractor|pecho)'                               THEN 3.8
           WHEN q.n ~ '(hack|hammer|hip.?thrust|empuje de cadera|pendulum)'                 THEN 3.4
           WHEN q.n ~ '(abductor|aductor|gluteo|gemelo|pantorrilla)'                        THEN 3.0
           WHEN q.n ~ '(barra|disco)'                                                       THEN 2.8
           WHEN q.n ~ '(kettlebell|pesa rusa)'                                              THEN 1.4
           WHEN q.n ~ '(balon|medicine)'                                                    THEN 0.8
           WHEN q.cat = 'funcional'                                                         THEN 0.8
           WHEN q.cat = 'bancos_racks'                                                      THEN 4.0
           WHEN q.cat = 'placas'                                                            THEN 4.2
           WHEN q.cat = 'discos'                                                            THEN 3.8
           WHEN q.cat = 'peso_libre'                                                        THEN 2.6
           ELSE 1.5
       END * (0.80 + 0.40 * q.r_uso) AS h_dia
FROM tmp_eq1 q;

CREATE TEMP TABLE tmp_eq ON COMMIT DROP AS
SELECT q.*,
       -- Se instalan justo antes de abrir (2-9 días) y se compraron 10-40 días antes de instalarse.
       p.apertura - (2 + floor(q.r_ins * 8))::int                                      AS instal,
       p.apertura - (2 + floor(q.r_ins * 8))::int - (10 + floor(q.r_adq * 30))::int    AS adq,
       -- Vida útil en meses (ver Analisis_Vida_Util_Equipos.md), algo menor si trabaja a ritmo alto.
       GREATEST(24, round(
           CASE
               WHEN q.grp = 'caminadora'                     THEN 84
               WHEN q.n ~ 'eliptic'                          THEN 96
               WHEN q.grp = 'bicicleta'                      THEN 108
               WHEN q.cat = 'cardio'                         THEN 96
               WHEN q.cat = 'placas'                         THEN 180
               WHEN q.cat = 'discos'                         THEN 216
               WHEN q.cat = 'peso_libre' AND q.n ~ '(balon|medicine)'         THEN 72
               WHEN q.cat = 'peso_libre' AND q.n ~ '(kettlebell|pesa rusa)'   THEN 144
               WHEN q.cat = 'peso_libre'                     THEN 240
               WHEN q.cat = 'bancos_racks'                   THEN 240
               WHEN q.n ~ '(banda|elastic|battle|cuerda|soga)'                THEN 48
               WHEN q.n ~ '(trx|suspension|bosu|foam|rodillo|colchoneta)'     THEN 60
               WHEN q.n ~ '(plyo|cajon)'                     THEN 96
               ELSE 72
           END * CASE WHEN q.h_dia >= 4 THEN 0.85 WHEN q.h_dia >= 3 THEN 0.92 ELSE 1.0 END / 6.0
       ) * 6)::int AS vida_meses
FROM tmp_eq2 q
CROSS JOIN tmp_p p;

UPDATE equipos e
   SET fecha_adquisicion = q.adq,
       fecha_instalacion = q.instal,
       vida_util_meses   = q.vida_meses
  FROM tmp_eq q
 WHERE e.id = q.id;

-- ---------------------------------------------------------------------------
-- 2) Mantenciones de rutina (sin fallas)
--    a) Inspección mensual del personal del CAF: el primer lunes de cada mes, costo $0.
--    b) Mantención trimestral del proveedor cada `cada_dias` días (valor `cuota_visita` por visita).
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_insp ON COMMIT DROP AS
SELECT (m + ((8 - EXTRACT(isodow FROM m)::int) % 7) * interval '1 day')::date AS dia
FROM tmp_p p
CROSS JOIN LATERAL generate_series(date_trunc('month', p.apertura)::date + interval '1 month',
                                   date_trunc('month', p.hoy)::date, interval '1 month') AS g(m)
WHERE (m + ((8 - EXTRACT(isodow FROM m)::int) % 7) * interval '1 day')::date < p.hoy;

INSERT INTO mantenimientos (
    equipo_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, proximo_mantenimiento, created_at, updated_at
)
SELECT r.equipo_id,
       'inspeccion',
       'Personal del CAF',
       'Servicio técnico interno',
       'Inspección mensual: revisión visual, limpieza, ajuste de pernos y prueba de funcionamiento. Sin hallazgos.',
       '[{"nombre": "Revisión de rutina (sin repuestos)", "cantidad": 1, "demo": "caf"}]'::jsonb,
       0,
       r.inicio,
       r.inicio + interval '4 minute',
       (date_trunc('month', r.dia) + interval '1 month')::date,
       r.inicio + interval '4 minute',
       r.inicio + interval '4 minute'
FROM (
    SELECT n.*,
           (n.dia::timestamp + interval '8 hour' + (n.rn - 1) * interval '3 minute') AT TIME ZONE 'America/Santiago' AS inicio
    FROM (
        SELECT v.dia, e.id AS equipo_id,
               row_number() OVER (PARTITION BY v.dia ORDER BY e.id) AS rn
        FROM tmp_insp v
        JOIN tmp_eq e ON e.instal <= v.dia
    ) n
) r;

CREATE TEMP TABLE tmp_visitas ON COMMIT DROP AS
SELECT k.k, (p.apertura + 30 + k.k * :cada_dias)::date AS dia
FROM tmp_p p
CROSS JOIN generate_series(0, 60) AS k(k)
WHERE p.apertura + 30 + k.k * :cada_dias < p.hoy - 2;

INSERT INTO mantenimientos (
    equipo_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, proximo_mantenimiento, created_at, updated_at
)
SELECT r.equipo_id,
       'preventivo',
       'Rodrigo Muñoz',
       'Proveedor de equipamiento',
       CASE WHEN r.es_cuota
            THEN 'Mantención trimestral del proveedor: lubricación, calibración y revisión de todas las máquinas del CAF (valor de la visita).'
            ELSE 'Mantención trimestral del proveedor: lubricación y revisión de esta máquina (incluida en el valor de la visita).' END,
       jsonb_build_array(jsonb_build_object(
           'nombre', CASE WHEN r.es_cuota THEN 'Mantención trimestral' ELSE 'Revisión incluida en la visita' END,
           'cantidad', 1,
           'demo', 'caf')),
       CASE WHEN r.es_cuota THEN :cuota_visita ELSE 0 END,
       r.inicio,
       r.inicio + interval '6 minute',
       r.dia + :cada_dias,
       r.inicio + interval '6 minute',
       r.inicio + interval '6 minute'
FROM (
    SELECT n.*,
           (n.dia::timestamp + interval '9 hour' + (n.rn - 1) * interval '6 minute') AT TIME ZONE 'America/Santiago' AS inicio,
           (n.rn = 1 + (n.k % n.total)) AS es_cuota   -- la cuota (si la hay) se registra una sola vez por visita
    FROM (
        SELECT v.k, v.dia, e.id AS equipo_id,
               row_number() OVER (PARTITION BY v.k ORDER BY e.id) AS rn,
               count(*)     OVER (PARTITION BY v.k)               AS total
        FROM tmp_visitas v
        JOIN tmp_eq e ON e.instal <= v.dia
    ) n
) r;

-- ---------------------------------------------------------------------------
-- 3) Uso de las máquinas: 2 franjas por día (8:30-13:30 y 13:30-18:30), lunes a sábado
--    Cada fila es uso CONSOLIDADO de la franja (horas en que la máquina estuvo ocupada), no
--    una pasada individual: así se mantienen unas decenas de miles de filas y el Panel responde rápido.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_ses ON COMMIT DROP AS
SELECT t.*,
       -- Horas de la franja = uso diario típico x día de la semana x temporada x arranque del CAF
       -- (primeras semanas más tranquilas) x azar x reparto mañana/tarde.
       LEAST(4.7,
             t.h_dia
             * (ARRAY[1.10, 1.12, 1.06, 1.04, 0.82, 0.42])[EXTRACT(isodow FROM t.dia)::int]
             * (ARRAY[0.30, 0.30, 0.85, 1.05, 1.10, 1.05, 0.55, 0.95, 0.98, 1.10, 1.12, 0.70])[EXTRACT(month FROM t.dia)::int]
             * (0.55 + 0.45 * LEAST(1.0, (t.dia - t.apertura) / 120.0))
             * (0.8 + 0.4 * t.r1)
             * CASE t.blq WHEN 1 THEN 0.42 ELSE 0.58 END
             * (0.75 + 0.5 * t.r2)) AS horas
FROM (
    SELECT e.id AS equipo_id, e.cat, e.h_dia, p.apertura, d.dia::date AS dia, b.blq,
           random() AS r1, random() AS r2, random() AS r3, random() AS r4
    FROM tmp_eq e
    CROSS JOIN tmp_p p
    CROSS JOIN LATERAL generate_series(GREATEST(p.apertura, e.instal)::timestamp, (p.hoy - 1)::timestamp, interval '1 day') AS d(dia)
    CROSS JOIN (VALUES (1), (2)) AS b(blq)
) t
WHERE EXTRACT(isodow FROM t.dia) <> 7                                   -- el CAF no abre los domingos
  AND NOT ((EXTRACT(month FROM t.dia), EXTRACT(day FROM t.dia)) IN (     -- feriados (aprox.)
        (1, 1), (5, 1), (5, 21), (6, 20), (6, 29), (7, 16), (8, 15), (9, 18), (9, 19),
        (10, 12), (10, 31), (11, 1), (12, 8), (12, 25)))
  AND t.r4 >= GREATEST(0, 0.5 - t.h_dia / 2.0);   -- las máquinas poco usadas se saltan algunas franjas

DELETE FROM tmp_ses WHERE horas < 0.05;

INSERT INTO sesiones_uso (
    equipo_id, origen, fecha_inicio, fecha_fin, duracion_segundos, cantidad_eventos,
    estado, metadata, created_at, updated_at
)
SELECT s.equipo_id,
       'manual'::origen_uso,
       s.inicio,
       s.inicio + round(s.horas * 3600)::int * interval '1 second',
       round(s.horas * 3600)::int,
       -- Cuántas pasadas individuales hay dentro de la franja (cardio ~28 min, placas ~9 min, etc.).
       GREATEST(1, round(s.horas * 60 / CASE s.cat WHEN 'cardio' THEN 28 WHEN 'placas' THEN 9 WHEN 'discos' THEN 11
                                                    WHEN 'peso_libre' THEN 12 WHEN 'bancos_racks' THEN 14 ELSE 8 END))::int,
       'cerrada',
       '{"demo": "caf", "consolidado": true}'::jsonb,
       s.inicio,
       s.inicio
FROM (
    SELECT t.*,
           -- La franja dura 5 horas (mañana desde las 8:30, tarde desde las 13:30); el uso cae en
           -- un punto al azar de ella y nunca pasa de las 13:30 ni de las 18:30.
           (t.dia::timestamp
             + CASE t.blq WHEN 1 THEN interval '8 hour 30 minute' ELSE interval '13 hour 30 minute' END
             + (5.0 - t.horas) * t.r3 * interval '1 hour')
             AT TIME ZONE 'America/Santiago' AS inicio
    FROM tmp_ses t
) s;

-- ---------------------------------------------------------------------------
-- 5) Incidencias solucionadas (desde el segundo año) y su mantención correctiva
--    El primer año no hay ninguna. `dia` = días después de la apertura.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_roles ON COMMIT DROP AS
SELECT 'polea'::text AS rol,
       (SELECT id FROM tmp_eq WHERE n ~ 'polea' ORDER BY id LIMIT 1) AS equipo_id
UNION ALL
SELECT 'cinta1', (SELECT id FROM tmp_eq WHERE grp = 'caminadora' ORDER BY id LIMIT 1)
UNION ALL
SELECT 'cinta2', COALESCE((SELECT id FROM tmp_eq WHERE grp = 'caminadora' ORDER BY id OFFSET 1 LIMIT 1),
                          (SELECT id FROM tmp_eq WHERE grp = 'caminadora' ORDER BY id LIMIT 1))
UNION ALL
SELECT 'bici', (SELECT id FROM tmp_eq WHERE grp = 'bicicleta' ORDER BY id LIMIT 1)
UNION ALL
SELECT 'banco', (SELECT id FROM tmp_eq WHERE n ~ '(banco|bench)' ORDER BY id LIMIT 1);

CREATE TEMP TABLE tmp_inc_def ON COMMIT DROP AS
SELECT row_number() OVER () AS k, d.*
FROM (VALUES
  -- rol, día tras apertura, hora, código de falla, prioridad, descripción, quién reporta, origen,
  -- días hasta solucionarla, qué se hizo, repuesto, costo (CLP), quién lo hizo
  ('polea',  427, '10:40', 'DESGASTE',       'baja',    'Desgaste de las poleas: el cable se siente áspero al recorrer.',
   'Personal del CAF', 'tecnico', 2, 'Cambio de las poleas desgastadas y lubricación del cable.', 'Poleas (2)', 38000, 'Rodrigo Muñoz'),
  ('cinta1', 468, '09:15', 'NO_ENCIENDE',    'urgente', 'La caminadora no prende.',
   'Estudiante', 'qr', 2, 'Cambio de fusible y revisión de la fuente de poder.', 'Fusible', 28000, 'Rodrigo Muñoz'),
  ('bici',   527, '17:05', 'OTRO',           'baja',    'El pedal de la bicicleta quedó suelto.',
   'Estudiante', 'qr', 1, 'Reapriete y ajuste del pedal.', 'Sin repuestos', 0, 'Personal del CAF'),
  ('polea',  571, '12:20', 'ROTA',           'urgente', 'Se cortó la polea: el cable se soltó y la máquina no se puede ocupar.',
   'Estudiante', 'qr', 4, 'Reemplazo del cable de acero y de la polea dañada.', 'Cable de acero y polea', 85000, 'Rodrigo Muñoz'),
  ('cinta2', 640, '16:30', 'SONIDO_EXTRANO', 'media',   'La banda hace ruido y se corre hacia un lado.',
   'Personal del CAF', 'tecnico', 1, 'Alineación y lubricación de la banda.', 'Lubricante', 18000, 'Rodrigo Muñoz'),
  ('banco',  690, '11:10', 'DESGASTE',       'baja',    'El tapiz del banco está gastado.',
   'Estudiante', 'qr', 5, 'Cambio del tapiz del banco.', 'Tapiz', 32000, 'Rodrigo Muñoz'),
  ('polea',  735, '14:45', 'SONIDO_EXTRANO', 'baja',    'Chirrido en las poleas al subir la carga.',
   'Estudiante', 'qr', 1, 'Lubricación y ajuste de las poleas.', 'Sin repuestos', 0, 'Personal del CAF'),
  ('cinta1', 780, '10:05', 'DESGASTE',       'baja',    'Desgaste de la banda de la caminadora.',
   'Personal del CAF', 'tecnico', 3, 'Cambio de la banda de la caminadora.', 'Banda', 52000, 'Rodrigo Muñoz')
) AS d(rol, dia, hora, codigo, prioridad, descripcion, reporta, origen, dias_res, hecho, repuesto, costo, tecnico);

-- Fechas reales: nunca en domingo (el CAF no abre) y solo si ya pasaron.
CREATE TEMP TABLE tmp_inc ON COMMIT DROP AS
SELECT d.*, r.equipo_id,
       ((x.dia_rep::timestamp + d.hora::time) AT TIME ZONE 'America/Santiago') AS reporte,
       ((x.dia_res::timestamp + time '15:30') AT TIME ZONE 'America/Santiago') AS solucion
FROM tmp_inc_def d
JOIN tmp_roles r ON r.rol = d.rol AND r.equipo_id IS NOT NULL
CROSS JOIN tmp_p p
CROSS JOIN LATERAL (
    SELECT a.dia_rep,
           (a.dia_rep + d.dias_res + CASE WHEN EXTRACT(isodow FROM a.dia_rep + d.dias_res) = 7 THEN 1 ELSE 0 END)::date AS dia_res
    FROM (SELECT (p.apertura + d.dia + CASE WHEN EXTRACT(isodow FROM p.apertura + d.dia) = 7 THEN 1 ELSE 0 END)::date AS dia_rep) a
) x
WHERE x.dia_res < p.hoy - 1;

INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por, prioridad, estado,
    fecha_reporte, fecha_resolucion, metadata, created_at, updated_at
)
SELECT i.equipo_id,
       COALESCE((SELECT id FROM tipos_falla WHERE codigo = i.codigo),
                (SELECT id FROM tipos_falla WHERE codigo = 'OTRO'),
                (SELECT MIN(id) FROM tipos_falla)),
       i.origen::origen_incidencia,
       i.descripcion,
       i.reporta,
       i.prioridad::prioridad_incidencia,
       'resuelta',
       i.reporte,
       i.solucion,
       jsonb_build_object('demo', 'caf', 'k', i.k),
       i.reporte,
       i.solucion
FROM tmp_inc i;

-- Mantención correctiva de cada incidencia, enlazada a ella y hecha el día en que se soluciona.
INSERT INTO mantenimientos (
    equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, proximo_mantenimiento, created_at, updated_at
)
SELECT i.equipo_id,
       inc.id,
       'correctivo',
       i.tecnico,
       CASE WHEN i.tecnico = 'Personal del CAF' THEN 'Servicio técnico interno' ELSE 'Proveedor de equipamiento' END,
       i.hecho,
       jsonb_build_array(jsonb_build_object('nombre', i.repuesto, 'cantidad', 1, 'demo', 'caf')),
       i.costo,
       i.solucion - interval '4 hour',
       i.solucion,
       NULL,
       i.solucion,
       i.solucion
FROM tmp_inc i
JOIN incidencias inc ON inc.metadata ->> 'demo' = 'caf' AND (inc.metadata ->> 'k')::int = i.k;

-- Mientras la máquina estuvo parada (falla urgente) no tuvo uso.
DELETE FROM sesiones_uso s
USING tmp_inc i
WHERE s.equipo_id = i.equipo_id
  AND i.prioridad = 'urgente'
  AND s.fecha_inicio >= i.reporte
  AND s.fecha_inicio < i.solucion;

COMMIT;

-- ---------------------------------------------------------------------------
-- Resumen (se imprime al ejecutar)
-- ---------------------------------------------------------------------------
\echo
\echo '== Filas creadas =='
SELECT (SELECT COUNT(*) FROM equipos WHERE estado <> 'retirado') AS maquinas,
       (SELECT COUNT(*) FROM incidencias WHERE estado <> 'resuelta') AS incidencias_abiertas,
       (SELECT COUNT(*) FROM incidencias) AS incidencias_total,
       (SELECT COUNT(*) FROM mantenimientos) AS mantenciones,
       (SELECT COUNT(*) FROM sesiones_uso) AS franjas_de_uso,
       (SELECT ROUND(SUM(duracion_segundos) / 3600.0) FROM sesiones_uso) AS horas_de_uso_total;

\echo
\echo '== Incidencias (todas solucionadas; ninguna en el primer año) =='
SELECT to_char(i.fecha_reporte AT TIME ZONE 'America/Santiago', 'YYYY-MM-DD') AS reportada,
       e.nombre AS maquina, t.nombre AS falla, i.prioridad, i.estado,
       to_char(i.fecha_resolucion AT TIME ZONE 'America/Santiago', 'YYYY-MM-DD') AS solucionada,
       m.costo_total AS costo_correctivo
FROM incidencias i
JOIN equipos e ON e.id = i.equipo_id
JOIN tipos_falla t ON t.id = i.tipo_falla_id
LEFT JOIN mantenimientos m ON m.incidencia_id = i.id
ORDER BY i.fecha_reporte;

\echo
\echo '== Costo de mantenciones (trimestral = visita; correctivas = reparaciones) =='
SELECT tipo, COUNT(*) AS registros, COALESCE(SUM(costo_total), 0) AS total_clp
FROM mantenimientos GROUP BY tipo ORDER BY tipo;

\echo
\echo '== Comprobación del horario (debe ser 8:30 a 18:30, sin domingos) =='
SELECT to_char(MIN((fecha_inicio AT TIME ZONE 'America/Santiago')::time), 'HH24:MI') AS primera_hora_de_inicio,
       to_char(MAX((fecha_fin    AT TIME ZONE 'America/Santiago')::time), 'HH24:MI') AS ultima_hora_de_termino,
       COUNT(*) FILTER (WHERE EXTRACT(isodow FROM fecha_inicio AT TIME ZONE 'America/Santiago') = 7) AS filas_en_domingo
FROM sesiones_uso;

\echo
\echo '== Horas de uso por tipo de máquina (promedio por máquina, desde la apertura) =='
SELECT e.categoria,
       COUNT(DISTINCT e.id) AS maquinas,
       ROUND(SUM(s.duracion_segundos) / 3600.0 / COUNT(DISTINCT e.id)) AS horas_por_maquina
FROM equipos e
JOIN sesiones_uso s ON s.equipo_id = e.id
GROUP BY e.categoria
ORDER BY horas_por_maquina DESC;

\echo
\echo '== Las 12 máquinas más usadas =='
SELECT e.codigo_activo, e.nombre, e.categoria,
       ROUND(SUM(s.duracion_segundos) / 3600.0) AS horas_uso,
       e.vida_util_meses
FROM equipos e
JOIN sesiones_uso s ON s.equipo_id = e.id
GROUP BY e.id
ORDER BY horas_uso DESC
LIMIT 12;

-- ---------------------------------------------------------------------------
-- DESHACER (opcional): vuelve a las fechas originales de las máquinas y quita el uso, las
-- mantenciones y las incidencias generadas. (Lo que se borró al principio NO se puede
-- recuperar con esto: para eso usa el respaldo que hiciste antes.)
--
--   BEGIN;
--   DELETE FROM sesiones_uso   WHERE metadata ->> 'demo' = 'caf';
--   DELETE FROM mantenimientos WHERE repuestos @> '[{"demo": "caf"}]'::jsonb;
--   DELETE FROM incidencias    WHERE metadata ->> 'demo' = 'caf';
--   UPDATE equipos e SET fecha_adquisicion = r.fecha_adquisicion, fecha_instalacion = r.fecha_instalacion,
--          vida_util_meses = r.vida_util_meses FROM respaldo_fechas_equipos r WHERE r.id = e.id;
--   COMMIT;
-- ---------------------------------------------------------------------------
