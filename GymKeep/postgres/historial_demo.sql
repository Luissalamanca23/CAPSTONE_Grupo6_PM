-- ============================================================================
-- historial_demo.sql
--
-- Le da "historia" al gimnasio (por defecto: abierto hace 2 anos y 8 meses) con datos de
-- DEMOSTRACION coherentes entre si, para que el Panel tenga con que inferir:
--
--   1. Fechas: las maquinas quedan instaladas justo antes de la apertura.
--   2. Vida util (vida_util_meses) de cada maquina, segun el tipo de equipo y lo usada que
--      es (ver Analisis_Vida_Util_Equipos.md).
--   3. USO: una fila de sesiones_uso por maquina, por dia y por franja (manana / tarde-noche).
--      Las maquinas mas pedidas (mancuernas, bancos, cintas, prensas, poleas) acumulan miles
--      de horas y las de nicho muy pocas: sirve para decidir que maquinas sumar si el gimnasio
--      se amplia o se abre otro local (seccion "Demanda" del Dashboard). Mas uso lunes-martes,
--      menos fines de semana y feriados, mas en marzo-abril y septiembre-noviembre.
--   4. INCIDENCIAS: pocas (alrededor de una cada dos semanas) y no todos los dias. Fallan
--      sobre todo las caminadoras, las bicicletas y las maquinas con polea; el resto casi no.
--      Se concentran en horario punta (17-21 h) y la reparacion se vuelve mas rapida con el tiempo.
--   5. MANTENCIONES y costos (pesos chilenos):
--        - PREVENTIVA: viene el encargado cada 60 dias, cobra una CUOTA FIJA (50.000) y revisa
--          todas las maquinas en la misma visita. La cuota se registra una sola vez por visita
--          (en una de las maquinas, rotando); las demas filas de la visita quedan en $0.
--        - CORRECTIVA: cada incidencia resuelta tiene su mantencion. Solo las reparaciones
--          que requieren repuesto o tecnico (piezas rotas, equipo que no enciende) tienen costo;
--          los ajustes menores los hace el personal del gimnasio ($0).
--        - El gasto total de todo el periodo no supera el TOPE configurable (por defecto 2.950.000).
--   6. "Hoy": 1 maquina en taller, 1 fuera de servicio, 2 reportes sin atender hace dias y
--      1 maquina con 3 fallas en el ultimo mes, para que se vean los avisos de "Atencion recomendada".
--
-- TODO LO QUE CREA ESTA MARCADO como demo ("demo": "historial3") y es seguro correrlo mas de
-- una vez: al empezar borra lo de la corrida anterior (y lo de los scripts antiguos
-- datos_demo_dashboard.sql / historial_3_anios.sql) y lo vuelve a generar con fechas
-- relativas a HOY. No toca incidencias, mantenciones ni sesiones que hayas creado a mano.
--
-- Funciona con las maquinas que tengas ingresadas (cualquier nombre, cualquier cantidad):
-- reconoce el tipo por categoria y por palabras del nombre ("cinta", "prensa", "polea"...).
--
-- Cambia en la tabla equipos (guarda antes el original en respaldo_fechas_equipos):
--   fecha_adquisicion, fecha_instalacion, vida_util_meses  (de todas las maquinas no retiradas)
--   estado de 2 maquinas (1 en taller, 1 fuera de servicio) para la demostracion.
-- Al final de este archivo hay un bloque "DESHACER".
--
-- Como ejecutarlo (con Docker levantado), desde la carpeta GymKeep, en PowerShell:
--
--   docker compose cp postgres\historial_demo.sql db:/tmp/historial_demo.sql
--   docker compose exec db psql -U gymkeep -d gymkeep -f /tmp/historial_demo.sql
--
-- (Se copia el archivo dentro del contenedor para que las tildes lleguen bien.)
-- Tarda unos segundos y genera ~140.000 filas de uso.
-- ============================================================================

\set ON_ERROR_STOP on
\encoding UTF8

-- ---- Ajustes (puedes cambiarlos) -------------------------------------------
-- Meses que lleva abierto el gimnasio (32 = 2 anos y 8 meses).
\set meses_abierto 32
-- Cada cuantos dias viene el encargado de las mantenciones preventivas.
\set cada_dias 60
-- Cuota fija de cada visita (revisa todas las maquinas), en CLP.
\set cuota_visita 50000
-- El gasto total demo en mantenciones no pasa de esto, en CLP.
\set tope_gasto 2950000
-- ----------------------------------------------------------------------------

BEGIN;

-- Cada corrida genera una variante distinta, con las mismas proporciones y los mismos patrones.
SELECT setseed(0.37);

-- ---------------------------------------------------------------------------
-- 0) Limpiar la corrida anterior (solo filas marcadas como demo)
-- ---------------------------------------------------------------------------
-- Las maquinas que la demo dejo "en taller" o "fuera de servicio" vuelven a operativo.
UPDATE equipos SET estado = 'operativo'
WHERE estado IN ('en_mantenimiento', 'fuera_de_servicio')
  AND id IN (SELECT equipo_id FROM incidencias WHERE metadata ->> 'demo' IN ('historial3', 'dashboard'));

DELETE FROM sesiones_uso   WHERE metadata ->> 'demo' = 'historial3';
DELETE FROM mantenimientos WHERE repuestos @> '[{"demo": "historial3"}]'::jsonb
                              OR repuestos @> '[{"demo": "dashboard"}]'::jsonb;
DELETE FROM incidencias    WHERE metadata ->> 'demo' IN ('historial3', 'dashboard');

-- Respaldo (solo la primera vez) de lo que este script modifica en equipos.
CREATE TABLE IF NOT EXISTS respaldo_fechas_equipos AS
SELECT id, fecha_adquisicion, fecha_instalacion, vida_util_meses, now() AS respaldado_en FROM equipos;

-- Fechas de referencia (hora de Chile).
CREATE TEMP TABLE tmp_p ON COMMIT DROP AS
SELECT (now() AT TIME ZONE 'America/Santiago')::date AS hoy,
       ((now() AT TIME ZONE 'America/Santiago')::date - (interval '1 month' * :meses_abierto))::date AS apertura;

-- ---------------------------------------------------------------------------
-- 1) Perfil de cada maquina: tipo, uso diario, fragilidad, fechas y vida util
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_eq0 ON COMMIT DROP AS
SELECT s.*,
       -- Tipo de equipo (las 6 categorias del gimnasio). Si una maquina aun trae una categoria
       -- antigua ("fuerza", "otro", vacia), se deduce del nombre.
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
           random() AS r_uso, random() AS r_frag, random() AS r_adq, random() AS r_ins
    FROM equipos e
    WHERE e.estado <> 'retirado'
) s;

CREATE TEMP TABLE tmp_eq1 ON COMMIT DROP AS
SELECT q.*,
       -- Grupo que concentra las fallas: caminadoras, bicicletas y maquinas con polea.
       CASE
           WHEN q.n ~ '(cinta|trotadora|caminadora|treadmill)'                                   THEN 'caminadora'
           WHEN q.n ~ '(bicicleta|bike|spinning)'                                                THEN 'bicicleta'
           WHEN q.cat IN ('placas', 'discos') AND q.n ~ '(polea|jalon|pulldown|cruce|cable|crossover|multiestacion|remo sentado)' THEN 'polea'
           ELSE 'otro'
       END AS grp
FROM tmp_eq0 q;

CREATE TEMP TABLE tmp_eq2 ON COMMIT DROP AS
SELECT q.*,
       -- Horas de uso en un dia habil tipico, segun lo "popular" que es ese tipo de maquina.
       CASE
           WHEN q.grp = 'caminadora'                                                        THEN 4.4
           WHEN q.grp = 'bicicleta'                                                         THEN 3.2
           WHEN q.n ~ 'eliptic'                                                             THEN 2.8
           WHEN q.n ~ '(skierg|ski erg|remadora|rower|escalador|stairmaster|maquina de remo|assault)' THEN 1.6
           WHEN q.cat = 'cardio'                                                            THEN 2.2
           WHEN q.n ~ 'soporte (para|de) '                                                  THEN 0.3
           WHEN q.n ~ '(mancuernas|dumbbells|juego de|set de)'                              THEN 5.0
           WHEN q.n ~ '(mancuerna|dumbbell)'                                                THEN 1.2
           WHEN q.n ~ 'banco' AND q.n ~ '(plano|inclin|declin|press)'                       THEN 4.6
           WHEN q.n ~ '(smith|multipower)'                                                  THEN 3.6
           WHEN q.n ~ '(jaula|rack|power)'                                                  THEN 4.2
           WHEN q.n ~ 'prensa'                                                              THEN 4.0
           WHEN q.grp = 'polea'                                                             THEN 3.9
           WHEN q.n ~ '(extension|cuadriceps|curl|femoral|isquio)'                          THEN 3.1
           WHEN q.n ~ '(pec ?deck|mariposa|contractor|pecho)'                               THEN 3.0
           WHEN q.n ~ '(hack|hammer|hip.?thrust|empuje de cadera|pendulum)'                 THEN 2.7
           WHEN q.n ~ '(abductor|aductor|gluteo|gemelo|pantorrilla)'                        THEN 2.4
           WHEN q.n ~ '(barra|disco)'                                                       THEN 2.6
           WHEN q.n ~ '(kettlebell|pesa rusa)'                                              THEN 1.4
           WHEN q.n ~ '(balon|medicine)'                                                    THEN 0.8
           WHEN q.cat = 'funcional'                                                         THEN 0.7
           WHEN q.cat = 'bancos_racks'                                                      THEN 2.8
           WHEN q.cat = 'placas'                                                            THEN 2.8
           WHEN q.cat = 'discos'                                                            THEN 2.4
           WHEN q.cat = 'peso_libre'                                                        THEN 2.4
           ELSE 1.5
       END * (0.75 + 0.5 * q.r_uso) AS h_dia,
       -- Fallas por ano de una maquina "normal" de su tipo: las caminadoras, las bicicletas y
       -- las maquinas con polea fallan mucho mas que el resto.
       CASE q.grp WHEN 'caminadora' THEN 1.7 WHEN 'bicicleta' THEN 1.5 WHEN 'polea' THEN 0.9
            ELSE CASE q.cat WHEN 'cardio' THEN 0.50 WHEN 'placas' THEN 0.18 WHEN 'discos' THEN 0.10
                            WHEN 'bancos_racks' THEN 0.07 WHEN 'peso_libre' THEN 0.04 ELSE 0.15 END
       END AS lam,
       -- 6 % de las maquinas son "problematicas" (1,5 veces mas fallas), 14 % algo mas fallosas.
       CASE WHEN q.r_frag < 0.06 THEN 1.5 WHEN q.r_frag < 0.20 THEN 1.2 ELSE 0.9 END AS fragil
FROM tmp_eq1 q;

CREATE TEMP TABLE tmp_eq ON COMMIT DROP AS
SELECT q.*,
       -- Se instalan justo antes de abrir (2-9 dias) y se compraron 10-40 dias antes de instalarse.
       p.apertura - (2 + floor(q.r_ins * 8))::int                               AS instal,
       p.apertura - (2 + floor(q.r_ins * 8))::int - (10 + floor(q.r_adq * 30))::int AS adq,
       -- Vida util en meses: referencia del tipo de equipo (ver Analisis_Vida_Util_Equipos.md)
       -- reducida si la maquina trabaja a un ritmo alto, redondeada a semestres.
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
-- 2) Parametros de falla por tipo de equipo (costos en CLP de HOY)
--    `pago`: probabilidad de que la reparacion requiera tecnico o repuesto (con costo). El resto
--    son ajustes menores que hace el personal del gimnasio ($0).
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_cat ON COMMIT DROP AS
WITH v(cat, codigo, peso, pago, costo_min, costo_rango, horas_min, horas_rango, descripciones, repuestos) AS (
    VALUES
    ('cardio', 'DESGASTE',        0.30, 0.25, 35000,  55000, 48,  96, ARRAY['Cambio de banda de rodamiento y lubricación del deck', 'Reemplazo de pedales y empuñaduras desgastadas'], ARRAY['Banda de rodamiento', 'Pedales y empuñaduras']),
    ('cardio', 'SONIDO_EXTRANO',  0.25, 0.20, 25000,  35000, 12,  48, ARRAY['Lubricación de rodillos y ajuste de correa', 'Cambio de rodamientos ruidosos'], ARRAY['Lubricante de silicona', 'Rodamientos']),
    ('cardio', 'ROTA',            0.15, 0.85, 90000, 130000, 72, 168, ARRAY['Reemplazo de motor de inclinación', 'Reparación de bastidor y cambio de rodillo trasero'], ARRAY['Motor de inclinación', 'Rodillo trasero']),
    ('cardio', 'NO_ENCIENDE',     0.30, 0.85, 70000, 110000, 24,  96, ARRAY['Cambio de fuente de poder', 'Reemplazo de tarjeta controladora'], ARRAY['Fuente de poder', 'Tarjeta controladora']),

    ('placas', 'DESGASTE',        0.40, 0.20, 25000,  45000, 24,  72, ARRAY['Cambio de cable de acero desgastado', 'Retapizado de respaldo y asiento'], ARRAY['Cable de acero', 'Tapiz y espuma']),
    ('placas', 'SONIDO_EXTRANO',  0.25, 0.10, 15000,  20000,  6,  36, ARRAY['Lubricación de guías y poleas', 'Cambio de pin selector y bujes'], ARRAY['Lubricante para guías', 'Bujes y pin selector']),
    ('placas', 'ROTA',            0.35, 0.80, 45000,  65000, 48, 120, ARRAY['Cambio de cable y poleas rotas', 'Soldadura y refuerzo de la estructura'], ARRAY['Cable de acero y poleas', 'Soporte reforzado']),

    ('discos', 'DESGASTE',        0.30, 0.15, 20000,  40000, 24,  72, ARRAY['Cambio de bujes de palanca', 'Reposición de topes de goma y manillas'], ARRAY['Bujes de bronce', 'Topes y manillas']),
    ('discos', 'SONIDO_EXTRANO',  0.25, 0.10, 15000,  20000,  6,  36, ARRAY['Engrase de ejes y ajuste de pernos', 'Cambio de rodamientos del carro'], ARRAY['Grasa para ejes', 'Rodamientos del carro']),
    ('discos', 'ROTA',            0.45, 0.75, 50000,  90000, 48, 144, ARRAY['Soldadura y refuerzo del brazo de palanca', 'Reemplazo de eje y pivote'], ARRAY['Eje y pivote', 'Placa de refuerzo']),

    ('peso_libre', 'DESGASTE',    0.50, 0.00,  8000,  20000, 12,  60, ARRAY['Reemplazo de grip y moleteado gastado', 'Recubrimiento de goma de mancuernas'], ARRAY['Grip de repuesto', 'Recubrimiento de goma']),
    ('peso_libre', 'SONIDO_EXTRANO', 0.15, 0.00, 5000, 8000,  6,  24, ARRAY['Ajuste de pernos del agarre', 'Limpieza y lubricación de manguitos de la barra'], ARRAY['Pernos y seguros', 'Aceite para barras']),
    ('peso_libre', 'ROTA',        0.35, 0.30, 15000,  25000, 24,  96, ARRAY['Cambio de mancuerna con rosca dañada', 'Reposición de barra doblada'], ARRAY['Mancuerna de reposición', 'Barra de reposición']),

    ('bancos_racks', 'DESGASTE',  0.45, 0.15, 20000,  40000, 24,  72, ARRAY['Retapizado de banco y cambio de espuma', 'Cambio de niveladores y tapas'], ARRAY['Tapiz y espuma', 'Niveladores y tapas']),
    ('bancos_racks', 'SONIDO_EXTRANO', 0.15, 0.05, 8000, 12000, 6,  36, ARRAY['Reapriete de pernos y ajuste de regulación', 'Lubricación de pasadores y rieles'], ARRAY['Pernos de alta resistencia', 'Lubricante para guías']),
    ('bancos_racks', 'ROTA',      0.40, 0.70, 30000,  60000, 48, 120, ARRAY['Reparación de soldadura en soporte J-hook', 'Cambio de pasador de regulación y refuerzo'], ARRAY['Soporte J-hook', 'Pasadores de regulación']),

    ('funcional', 'DESGASTE',     0.50, 0.00,  8000,  15000, 12,  48, ARRAY['Reposición de bandas elásticas fatigadas', 'Cambio de correas y mosquetones'], ARRAY['Bandas elásticas', 'Correas y mosquetones']),
    ('funcional', 'SONIDO_EXTRANO', 0.05, 0.00, 5000, 8000,  6,  24, ARRAY['Ajuste de anclajes', 'Lubricación de poleas y mosquetones'], ARRAY['Anclajes', 'Lubricante']),
    ('funcional', 'ROTA',         0.45, 0.30, 10000,  20000, 12,  72, ARRAY['Reposición de soga deshilachada', 'Reemplazo de caja pliométrica quebrada'], ARRAY['Soga de reposición', 'Caja pliométrica'])
)
SELECT v.*,
       -- Tramo [ac_ini, ac_fin) de cada tipo de falla dentro de su categoria (para sortear con un numero al azar).
       round(COALESCE(sum(peso) OVER (PARTITION BY cat ORDER BY codigo ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
             / sum(peso) OVER (PARTITION BY cat), 6) AS ac_ini,
       CASE WHEN row_number() OVER (PARTITION BY cat ORDER BY codigo DESC) = 1 THEN 2.0
            ELSE round(sum(peso) OVER (PARTITION BY cat ORDER BY codigo) / sum(peso) OVER (PARTITION BY cat), 6) END AS ac_fin
FROM v;

-- ---------------------------------------------------------------------------
-- 3) Incidencias desde la apertura
--    Cada semana, cada maquina tiene una probabilidad de fallar que crece con su uso, su
--    fragilidad y su edad (desgaste), ademas de la tasa base de su tipo.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_sem ON COMMIT DROP AS
SELECT row_number() OVER () AS i, s.*
FROM (
    SELECT e.id AS equipo_id, e.cat, e.h_dia, e.instal,
           date_trunc('week', now() AT TIME ZONE 'America/Santiago') - w.w * interval '7 days' AS inicio_local,
           LEAST(0.30,
                 e.lam / 52.0
                 * CASE WHEN (CURRENT_DATE - e.instal) - w.w * 7 < 182 THEN 0.5
                        WHEN (CURRENT_DATE - e.instal) - w.w * 7 < 365 THEN 0.7
                        WHEN (CURRENT_DATE - e.instal) - w.w * 7 < 730 THEN 1.0
                        ELSE 1.0 + 0.35 * (((CURRENT_DATE - e.instal) - w.w * 7) / 365.0 - 2) END
                 * LEAST(2.2, GREATEST(0.4, power(e.h_dia / 3.0, 0.7)))
                 * e.fragil) AS p,
           random() AS r_p,
           random() AS r_dia,   random() AS r_hora,  random() AS r_hora2, random() AS r_min,
           random() AS r_tipo,  random() AS r_res,   random() AS r_estado, random() AS r_nombre,
           random() AS r_desc,  random() AS r_origen
    FROM tmp_eq e
    CROSS JOIN generate_series(0, 200) AS w(w)
    WHERE (date_trunc('week', now() AT TIME ZONE 'America/Santiago') - w.w * interval '7 days')::date >= e.instal + 14
) s
WHERE s.r_p < s.p;

CREATE TEMP TABLE tmp_hist ON COMMIT DROP AS
WITH base AS (
    SELECT a.*, c.codigo, c.horas_min, c.horas_rango,
           -- Mas fallas al inicio de la semana: lunes 22 %, martes 18 %...
           CASE WHEN a.r_dia < 0.22 THEN 0 WHEN a.r_dia < 0.40 THEN 1 WHEN a.r_dia < 0.55 THEN 2
                WHEN a.r_dia < 0.70 THEN 3 WHEN a.r_dia < 0.82 THEN 4 WHEN a.r_dia < 0.92 THEN 5 ELSE 6 END AS dia,
           -- Horario punta: tarde (17-20 h) 55 %, manana (7-10 h) 25 %, resto del dia 20 %.
           CASE WHEN a.r_hora < 0.55 THEN 17 + floor(a.r_hora2 * 4)
                WHEN a.r_hora < 0.80 THEN 7 + floor(a.r_hora2 * 4)
                ELSE 11 + floor(a.r_hora2 * 6) END::int AS hora
    FROM tmp_sem a
    JOIN tmp_cat c ON c.cat = a.cat AND a.r_tipo >= c.ac_ini AND a.r_tipo < c.ac_fin
),
con_fecha AS (
    SELECT b.*,
           ((b.inicio_local + b.dia * interval '1 day')
             + b.hora * interval '1 hour' + floor(b.r_min * 60) * interval '1 minute')
             AT TIME ZONE 'America/Santiago' AS fecha_reporte
    FROM base b
),
con_horas AS (
    SELECT f.*,
           EXTRACT(EPOCH FROM (now() - f.fecha_reporte)) / 3600.0 AS horas_atras,
           -- Los arreglos antiguos tardaban mas: el factor va de 1,0 (apertura) a 0,5 (reciente).
           (f.horas_min + f.r_res * f.horas_rango)
             * (0.5 + 0.5 * LEAST(EXTRACT(EPOCH FROM (now() - f.fecha_reporte)) / 86400.0, 975) / 975.0) AS horas_res
    FROM con_fecha f
    WHERE f.fecha_reporte < now() - interval '3 hours'
      AND f.fecha_reporte >= (SELECT apertura FROM tmp_p)
)
SELECT h.*,
       CASE WHEN h.horas_atras < 48                                     THEN CASE WHEN h.r_estado < 0.4 THEN 'en_proceso' ELSE 'pendiente' END
            WHEN h.r_estado < 0.06                                      THEN 'descartada'
            WHEN h.fecha_reporte + h.horas_res * interval '1 hour' > now() - interval '1 hour' THEN 'en_proceso'
            ELSE 'resuelta' END AS estado
FROM con_horas h;

INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por,
    prioridad, estado, fecha_reporte, fecha_resolucion, metadata, created_at, updated_at
)
SELECT h.equipo_id,
       tf.id,
       (CASE WHEN h.r_origen < 0.72 THEN 'qr' ELSE 'tecnico' END)::origen_incidencia,
       (CASE h.codigo
            WHEN 'DESGASTE'       THEN ARRAY['Se nota desgaste visible en el tapiz y las piezas de agarre', 'Piezas con desgaste notorio; conviene revisarla pronto']
            WHEN 'SONIDO_EXTRANO' THEN ARRAY['Hace un ruido metálico al usarla', 'Vibración y chirrido durante el uso']
            WHEN 'ROTA'           THEN ARRAY['Se rompió una pieza y no se puede usar', 'Quedó fuera de uso por daño físico']
            ELSE                       ARRAY['No enciende al presionar el botón de inicio', 'La consola quedó en negro y no responde']
        END)[1 + floor(h.r_desc * 2)::int],
       CASE WHEN h.r_origen < 0.72
            THEN (ARRAY['Camila Rojas', 'Matías Vega', 'Fernanda Castro', 'Ignacio Soto', 'Juan Pérez', 'María López',
                        'Carlos Díaz', 'Valentina Araya', 'Sebastián Núñez', 'Javiera Pino'])[1 + floor(h.r_nombre * 10)::int]
            ELSE (ARRAY['Pablo Soto', 'Daniela Vera', 'Rodrigo Muñoz'])[1 + floor(h.r_nombre * 3)::int] END,
       tf.prioridad_base,
       h.estado::estado_incidencia,
       h.fecha_reporte,
       CASE h.estado
            WHEN 'resuelta'   THEN h.fecha_reporte + h.horas_res * interval '1 hour'
            WHEN 'descartada' THEN h.fecha_reporte + (4 + h.r_res * 40) * interval '1 hour'
       END,
       jsonb_build_object('demo', 'historial3', 'n', h.i),
       h.fecha_reporte,
       COALESCE(CASE h.estado WHEN 'resuelta'   THEN h.fecha_reporte + h.horas_res * interval '1 hour'
                              WHEN 'descartada' THEN h.fecha_reporte + (4 + h.r_res * 40) * interval '1 hour' END,
                h.fecha_reporte)
FROM tmp_hist h
JOIN tipos_falla tf ON tf.codigo = h.codigo;

-- ---------------------------------------------------------------------------
-- 4) Situaciones de HOY (para los avisos de "Atencion recomendada")
--    Sobre las maquinas que mas fallan: caminadoras, bicicletas y maquinas con polea.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_roles (rol text, equipo_id bigint) ON COMMIT DROP;

INSERT INTO tmp_roles
SELECT 'pend_alta', id FROM tmp_eq WHERE cat = 'cardio'
ORDER BY (grp = 'caminadora') DESC, (grp = 'bicicleta') DESC, h_dia DESC, id LIMIT 1;

INSERT INTO tmp_roles
SELECT 'taller', id FROM tmp_eq
WHERE cat = 'cardio' AND id NOT IN (SELECT equipo_id FROM tmp_roles)
ORDER BY (grp = 'bicicleta') DESC, (grp = 'caminadora') DESC, h_dia DESC, id LIMIT 1;

INSERT INTO tmp_roles
SELECT 'pend_media', id FROM tmp_eq
WHERE cat IN ('placas', 'discos') AND id NOT IN (SELECT equipo_id FROM tmp_roles)
ORDER BY (grp = 'polea') DESC, h_dia DESC, id LIMIT 1;

INSERT INTO tmp_roles
SELECT 'reincidente', id FROM tmp_eq
WHERE cat IN ('placas', 'discos') AND id NOT IN (SELECT equipo_id FROM tmp_roles)
ORDER BY (grp = 'polea') DESC, h_dia DESC, id LIMIT 1;

-- Para que las fallas de "hoy" no choquen con las generadas al azar, se descartan estas
-- ultimas en esas maquinas durante el ultimo mes.
DELETE FROM incidencias
WHERE metadata ->> 'demo' = 'historial3'
  AND fecha_reporte > now() - interval '32 days'
  AND equipo_id IN (SELECT equipo_id FROM tmp_roles);

INSERT INTO incidencias (
    equipo_id, tipo_falla_id, origen, descripcion, reportado_por,
    prioridad, estado, fecha_reporte, fecha_resolucion, metadata, created_at, updated_at
)
SELECT ro.equipo_id, tf.id, 'qr'::origen_incidencia, v.descripcion, v.reportado_por,
       v.prioridad::prioridad_incidencia, v.estado::estado_incidencia,
       now() - v.dias_atras * interval '1 day',
       CASE WHEN v.horas_res IS NOT NULL THEN now() - v.dias_atras * interval '1 day' + v.horas_res * interval '1 hour' END,
       '{"demo": "historial3"}'::jsonb,
       now() - v.dias_atras * interval '1 day',
       COALESCE(now() - v.dias_atras * interval '1 day' + v.horas_res * interval '1 hour', now() - v.dias_atras * interval '1 day')
FROM (
    VALUES
        ('taller',      'ROTA',           'alta',  'en_proceso', 4.0::numeric, NULL::numeric, 'Se rompió una pieza y quedó sin uso; el técnico la tiene en diagnóstico.', 'Camila Rojas'),
        ('pend_alta',   'NO_ENCIENDE',    'alta',  'pendiente',  3.2,          NULL,          'El panel no responde desde el fin de semana, no enciende.',                 'Ignacio Soto'),
        ('pend_media',  'DESGASTE',       'media', 'pendiente',  2.5,          NULL,          'El cable de la polea está deshilachado; hay que cambiarlo.',                'Matías Vega'),
        ('reincidente', 'DESGASTE',       'baja',  'resuelta',  26.0,          40,            'Desgaste visible en el cable, se traba un poco al subir el peso.',          'Valentina Araya'),
        ('reincidente', 'SONIDO_EXTRANO', 'media', 'resuelta',  15.0,          30,            'Vuelve a hacer ruido metálico en cada repetición.',                         'Juan Pérez'),
        ('reincidente', 'ROTA',           'alta',  'en_proceso',  6.0,         NULL,          'Se cortó el cable: es la tercera falla del mes.',                           'María López')
) AS v(rol, tipo, prioridad, estado, dias_atras, horas_res, descripcion, reportado_por)
JOIN tmp_roles ro ON ro.rol = v.rol
JOIN tipos_falla tf ON tf.codigo = v.tipo;

-- La maquina en taller y la que no enciende se ven en el estado del equipo.
UPDATE equipos SET estado = 'en_mantenimiento' WHERE id IN (SELECT equipo_id FROM tmp_roles WHERE rol = 'taller');
UPDATE equipos SET estado = 'fuera_de_servicio' WHERE id IN (SELECT equipo_id FROM tmp_roles WHERE rol = 'pend_alta');

-- ---------------------------------------------------------------------------
-- 5) Mantencion CORRECTIVA de cada incidencia resuelta
--    Con tecnico o repuesto (cuesta) solo las reparaciones que lo requieren; el resto son ajustes
--    del personal del gimnasio ($0).
-- ---------------------------------------------------------------------------
INSERT INTO mantenimientos (
    equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, created_at, updated_at
)
SELECT x.equipo_id,
       x.id,
       'correctivo',
       CASE WHEN x.pagada THEN (ARRAY['Rodrigo Muñoz', 'Pablo Soto', 'Daniela Vera'])[1 + floor(x.r_tec * 3)::int]
            ELSE 'Personal del gimnasio' END,
       CASE WHEN NOT x.pagada THEN 'Servicio técnico interno'
            WHEN x.cat = 'cardio' AND x.r_prov < 0.75 THEN 'TecnoFit Servicios'
            WHEN x.r_prov < 0.5 THEN 'TecnoFit Servicios'
            ELSE 'Mantenciones del Sur Ltda.' END,
       CASE WHEN x.pagada THEN x.descripciones[1 + floor(x.r_desc * 2)::int]
            ELSE 'Ajuste menor realizado por el personal del gimnasio' END,
       jsonb_build_array(jsonb_build_object(
           'nombre', CASE WHEN x.pagada THEN x.repuestos[1 + floor(x.r_desc * 2)::int] ELSE 'Ajuste menor (sin repuesto)' END,
           'cantidad', 1,
           'demo', 'historial3')),
       CASE WHEN x.pagada THEN round((x.costo_min + x.r_costo * x.costo_rango) / 1000) * 1000 ELSE 0 END,
       LEAST(x.fecha_reporte + (2 + x.r_inicio * 6) * interval '1 hour', x.fecha_resolucion),
       x.fecha_resolucion,
       x.fecha_resolucion,
       x.fecha_resolucion
FROM (
    SELECT i.id, i.equipo_id, i.fecha_reporte, i.fecha_resolucion, q.cat,
           c.costo_min, c.costo_rango, c.descripciones, c.repuestos,
           random() < c.pago AS pagada,
           random() AS r_tec, random() AS r_prov, random() AS r_desc, random() AS r_costo, random() AS r_inicio
    FROM incidencias i
    JOIN tipos_falla tf ON tf.id = i.tipo_falla_id
    JOIN tmp_eq q ON q.id = i.equipo_id
    JOIN tmp_cat c ON c.cat = q.cat AND c.codigo = tf.codigo
    WHERE i.metadata ->> 'demo' = 'historial3'
      AND i.estado = 'resuelta'
      AND i.fecha_resolucion IS NOT NULL
) x;

-- Mantencion abierta (en taller) de la maquina "en mantenimiento".
INSERT INTO mantenimientos (
    equipo_id, incidencia_id, tipo, tecnico, proveedor, descripcion, repuestos,
    fecha_inicio, created_at, updated_at
)
SELECT i.equipo_id, i.id, 'correctivo', 'Rodrigo Muñoz', 'TecnoFit Servicios',
       'Equipo en taller: diagnóstico y reparación en curso',
       '[{"nombre": "Diagnóstico", "cantidad": 1, "demo": "historial3"}]'::jsonb,
       i.fecha_reporte + interval '6 hour', i.fecha_reporte + interval '6 hour', i.fecha_reporte + interval '6 hour'
FROM incidencias i
JOIN tmp_roles ro ON ro.equipo_id = i.equipo_id AND ro.rol = 'taller'
WHERE i.metadata ->> 'demo' = 'historial3' AND i.estado = 'en_proceso' AND i.fecha_reporte > now() - interval '10 days';

-- ---------------------------------------------------------------------------
-- 6) Mantencion PREVENTIVA por visita del encargado (cuota fija, revisa todas las maquinas)
--    Cada `cada_dias` dias, la ultima hace ~6 semanas. En cada visita hay una fila por maquina
--    revisada (para que cada una tenga su historial), pero la cuota se registra UNA sola vez
--    por visita: en una maquina distinta cada vez; las demas filas quedan en $0.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE tmp_visitas ON COMMIT DROP AS
SELECT k.k,
       (p.hoy - 41 - k.k * :cada_dias + CASE WHEN k.k = 0 THEN 0 ELSE floor(random() * 7)::int - 3 END)::date AS dia
FROM tmp_p p
CROSS JOIN generate_series(0, 60) AS k(k)
WHERE p.hoy - 41 - k.k * :cada_dias >= p.apertura + 30;

INSERT INTO mantenimientos (
    equipo_id, tipo, tecnico, proveedor, descripcion, repuestos,
    costo_total, fecha_inicio, fecha_fin, proximo_mantenimiento, created_at, updated_at
)
SELECT r.equipo_id,
       'preventivo',
       'Rodrigo Muñoz',
       'TecnoFit Servicios',
       CASE WHEN r.es_cuota
            THEN 'Visita de mantención preventiva general (cuota fija): revisión y lubricación de todas las máquinas del gimnasio'
            ELSE 'Visita de mantención preventiva general: revisión de esta máquina (incluida en la cuota de la visita)' END,
       jsonb_build_array(jsonb_build_object(
           'nombre', CASE WHEN r.es_cuota THEN 'Cuota de visita preventiva' ELSE 'Revisión incluida en la cuota' END,
           'cantidad', 1,
           'demo', 'historial3')),
       CASE WHEN r.es_cuota THEN :cuota_visita ELSE 0 END,
       r.inicio,
       r.inicio + interval '3 minute',
       r.dia + :cada_dias,
       r.inicio + interval '3 minute',
       r.inicio + interval '3 minute'
FROM (
    SELECT n.*,
           (n.dia::timestamp + interval '9 hour 30 minute' + (n.rn - 1) * interval '4 minute') AT TIME ZONE 'America/Santiago' AS inicio,
           (n.rn = 1 + (n.k % n.total)) AS es_cuota
    FROM (
        SELECT v.k, v.dia, e.id AS equipo_id,
               row_number() OVER (PARTITION BY v.k ORDER BY e.id) AS rn,
               count(*)     OVER (PARTITION BY v.k)               AS total
        FROM tmp_visitas v
        JOIN tmp_eq e ON e.instal <= v.dia
    ) n
) r;

-- ---------------------------------------------------------------------------
-- 7) Tope de gasto: si por azar el total demo supera `tope_gasto`, se bajan proporcionalmente
--    las reparaciones con costo (la cuota de las visitas no se toca).
-- ---------------------------------------------------------------------------
WITH t AS (
    SELECT COALESCE(sum(costo_total) FILTER (WHERE tipo = 'preventivo'), 0) AS prev,
           COALESCE(sum(costo_total) FILTER (WHERE tipo = 'correctivo'), 0) AS corr
    FROM mantenimientos
    WHERE repuestos @> '[{"demo": "historial3"}]'::jsonb
)
UPDATE mantenimientos m
   SET costo_total = floor(m.costo_total * GREATEST(0, (:tope_gasto - t.prev)) / t.corr / 1000) * 1000
  FROM t
 WHERE m.tipo = 'correctivo'
   AND m.repuestos @> '[{"demo": "historial3"}]'::jsonb
   AND m.costo_total > 0
   AND t.corr > 0
   AND t.prev + t.corr > :tope_gasto;

-- ---------------------------------------------------------------------------
-- 8) Uso de las maquinas: 2 franjas por dia (manana y tarde-noche) desde la apertura
--    Cada fila es uso CONSOLIDADO de la franja (horas en que la maquina estuvo ocupada), no
--    una pasada individual: asi se mantienen ~140.000 filas y el Panel responde rapido.
-- ---------------------------------------------------------------------------
-- Dias en que la maquina estuvo detenida: reparaciones y, si es ROTA / NO_ENCIENDE, desde
-- que se reporto la falla hasta que se arreglo.
CREATE TEMP TABLE tmp_baja ON COMMIT DROP AS
SELECT DISTINCT b.equipo_id, b.dia
FROM (
    SELECT i.equipo_id, d::date AS dia
    FROM incidencias i
    JOIN tipos_falla tf ON tf.id = i.tipo_falla_id AND tf.codigo IN ('ROTA', 'NO_ENCIENDE')
    CROSS JOIN LATERAL generate_series(
        (i.fecha_reporte AT TIME ZONE 'America/Santiago')::date::timestamp,
        (COALESCE(i.fecha_resolucion, now()) AT TIME ZONE 'America/Santiago')::date::timestamp,
        interval '1 day') AS d
    WHERE i.metadata ->> 'demo' = 'historial3' AND i.estado <> 'descartada'
    UNION
    SELECT m.equipo_id, d::date
    FROM mantenimientos m
    CROSS JOIN LATERAL generate_series(
        (m.fecha_inicio AT TIME ZONE 'America/Santiago')::date::timestamp,
        (COALESCE(m.fecha_fin, now()) AT TIME ZONE 'America/Santiago')::date::timestamp,
        interval '1 day') AS d
    WHERE m.tipo = 'correctivo' AND m.repuestos @> '[{"demo": "historial3"}]'::jsonb
) b;
CREATE INDEX ON tmp_baja (equipo_id, dia);

CREATE TEMP TABLE tmp_ses ON COMMIT DROP AS
SELECT t.*,
       -- Horas de la franja = uso diario tipico x dia de la semana x temporada x crecimiento
       -- del gimnasio (arranca al 80 % de la demanda actual) x azar x reparto manana/tarde.
       LEAST(5.0,
             t.h_dia
             * (ARRAY[1.12, 1.10, 1.05, 1.00, 0.85, 0.55, 0.35])[EXTRACT(isodow FROM t.dia)::int]
             * (ARRAY[0.80, 0.78, 1.05, 1.08, 1.05, 0.95, 0.92, 1.00, 1.08, 1.12, 1.10, 0.88])[EXTRACT(month FROM t.dia)::int]
             * (0.80 + 0.20 * LEAST(1.0, (t.dia - t.apertura) / 975.0))
             * (0.8 + 0.4 * t.r1)
             * CASE t.blq WHEN 1 THEN 0.38 ELSE 0.62 END
             * (0.75 + 0.5 * t.r2)) AS horas
FROM (
    SELECT e.id AS equipo_id, e.cat, e.h_dia, p.apertura, d.dia::date AS dia, b.blq,
           random() AS r1, random() AS r2, random() AS r3, random() AS r4
    FROM tmp_eq e
    CROSS JOIN tmp_p p
    CROSS JOIN LATERAL generate_series(p.apertura::timestamp, (p.hoy - 1)::timestamp, interval '1 day') AS d(dia)
    CROSS JOIN (VALUES (1), (2)) AS b(blq)
) t
WHERE NOT ((EXTRACT(month FROM t.dia), EXTRACT(day FROM t.dia)) IN ((1, 1), (5, 1), (9, 18), (12, 25)))
  AND t.r4 >= GREATEST(0, 0.5 - t.h_dia / 2.0);   -- las maquinas poco usadas se saltan algunas franjas

DELETE FROM tmp_ses s USING tmp_baja b WHERE b.equipo_id = s.equipo_id AND b.dia = s.dia;
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
       -- Cuantas pasadas individuales hay dentro de la franja (cardio ~28 min, placas ~9 min, etc.).
       GREATEST(1, round(s.horas * 60 / CASE s.cat WHEN 'cardio' THEN 28 WHEN 'placas' THEN 9 WHEN 'discos' THEN 11
                                                    WHEN 'peso_libre' THEN 12 WHEN 'bancos_racks' THEN 14 ELSE 8 END))::int,
       'cerrada',
       '{"demo": "historial3", "consolidado": true}'::jsonb,
       s.inicio,
       s.inicio
FROM (
    SELECT t.*,
           (t.dia::timestamp
             + CASE t.blq WHEN 1 THEN interval '7 hour' + t.r3 * interval '90 minute'
                          ELSE interval '16 hour 30 minute' + t.r3 * interval '30 minute' END)
             AT TIME ZONE 'America/Santiago' AS inicio
    FROM tmp_ses t
) s;

COMMIT;

-- ---------------------------------------------------------------------------
-- Resumen (se imprime al ejecutar)
-- ---------------------------------------------------------------------------
\echo
\echo '== Filas creadas =='
SELECT (SELECT COUNT(*) FROM incidencias    WHERE metadata ->> 'demo' = 'historial3') AS incidencias,
       (SELECT COUNT(*) FROM mantenimientos WHERE repuestos @> '[{"demo": "historial3"}]'::jsonb) AS mantenciones,
       (SELECT COUNT(*) FROM sesiones_uso   WHERE metadata ->> 'demo' = 'historial3') AS franjas_de_uso,
       (SELECT ROUND(SUM(duracion_segundos) / 3600.0) FROM sesiones_uso WHERE metadata ->> 'demo' = 'historial3') AS horas_de_uso_total;

\echo
\echo '== Gasto total en mantenciones (CLP) =='
SELECT COALESCE(SUM(costo_total) FILTER (WHERE tipo = 'preventivo'), 0) AS cuotas_preventivas,
       COALESCE(SUM(costo_total) FILTER (WHERE tipo = 'correctivo'), 0) AS reparaciones,
       COALESCE(SUM(costo_total), 0) AS total,
       COUNT(*) FILTER (WHERE tipo = 'correctivo' AND costo_total > 0) AS reparaciones_con_costo
FROM mantenimientos
WHERE repuestos @> '[{"demo": "historial3"}]'::jsonb;

\echo
\echo '== Incidencias por tipo de maquina =='
SELECT CASE
           WHEN translate(lower(e.nombre), 'áéíóúüñ', 'aeiouun') ~ '(cinta|trotadora|caminadora|treadmill)' THEN 'Caminadoras'
           WHEN translate(lower(e.nombre), 'áéíóúüñ', 'aeiouun') ~ '(bicicleta|bike|spinning)' THEN 'Bicicletas'
           WHEN translate(lower(e.nombre), 'áéíóúüñ', 'aeiouun') ~ '(polea|jalon|pulldown|cruce|cable|crossover|multiestacion|remo sentado)' THEN 'Máquinas con polea'
           ELSE 'Resto' END AS grupo,
       COUNT(*) AS incidencias
FROM incidencias i JOIN equipos e ON e.id = i.equipo_id
WHERE i.metadata ->> 'demo' = 'historial3'
GROUP BY 1 ORDER BY 2 DESC;

\echo
\echo '== Las 12 maquinas mas usadas (horas de uso desde la apertura) y su vida util =='
SELECT e.codigo_activo, e.nombre, e.categoria,
       ROUND(SUM(s.duracion_segundos) / 3600.0) AS horas_uso,
       ROUND(SUM(s.duracion_segundos) / 3600.0 / GREATEST(1, CURRENT_DATE - e.fecha_instalacion), 1) AS horas_por_dia,
       e.vida_util_meses AS vida_util_meses,
       (SELECT COUNT(*) FROM incidencias i WHERE i.equipo_id = e.id AND i.metadata ->> 'demo' = 'historial3') AS incidencias
FROM equipos e
JOIN sesiones_uso s ON s.equipo_id = e.id AND s.metadata ->> 'demo' = 'historial3'
GROUP BY e.id
ORDER BY horas_uso DESC
LIMIT 12;

-- ---------------------------------------------------------------------------
-- DESHACER (opcional): copia y pega estas lineas en psql para quitar TODO lo demo y volver a
-- las fechas originales de las maquinas.
--
--   BEGIN;
--   DELETE FROM sesiones_uso   WHERE metadata ->> 'demo' = 'historial3';
--   DELETE FROM mantenimientos WHERE repuestos @> '[{"demo": "historial3"}]'::jsonb;
--   DELETE FROM incidencias    WHERE metadata ->> 'demo' = 'historial3';
--   UPDATE equipos e SET fecha_adquisicion = r.fecha_adquisicion, fecha_instalacion = r.fecha_instalacion,
--          vida_util_meses = r.vida_util_meses FROM respaldo_fechas_equipos r WHERE r.id = e.id;
--   UPDATE equipos SET estado = 'operativo' WHERE estado IN ('en_mantenimiento', 'fuera_de_servicio');
--   COMMIT;
-- ---------------------------------------------------------------------------
