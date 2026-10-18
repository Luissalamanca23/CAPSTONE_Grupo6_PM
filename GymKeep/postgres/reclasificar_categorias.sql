-- ============================================================================
-- reclasificar_categorias.sql
--
-- Pasa las maquinas YA INGRESADAS al esquema de 6 categorias del gimnasio:
--
--   cardio        Equipo de Cardio                    (cintas, bicicletas, eliptica, remo, escaladora, skierg)
--   placas        Maquinas de Placas / Guiadas        (selector de peso con pin y poleas)
--   discos        Maquinas de Carga de Discos         (prensa 45, hack, hammer, hip thrust...)
--   peso_libre    Peso Libre                          (mancuernas, barras, discos, kettlebells, balones)
--   bancos_racks  Bancos y Soportes (Racks)           (bancos, jaula, smith, power tower, predicador)
--   funcional     Equipo Funcional y Accesorios       (bandas, battle ropes, plyo box, TRX, bosu, foam roller)
--
-- Como decide: lee el NOMBRE de cada maquina (sin tildes ni mayusculas) y aplica reglas por
-- palabras clave, en este orden: funcional -> bancos/racks -> discos -> cardio -> peso libre ->
-- placas. La primera regla que calza gana. Si ninguna calza, la maquina NO se toca y queda en la
-- lista final "sin clasificar" para corregirla a mano con el boton Editar del panel.
--
-- Seguro de correr varias veces. Antes de cambiar nada guarda la categoria anterior en
-- respaldo_categorias_equipos (solo la primera vez), por si quieres volver atras:
--     UPDATE equipos e SET categoria = r.categoria
--       FROM respaldo_categorias_equipos r WHERE r.id = e.id;
--
-- Ejecutar (desde la carpeta GymKeep, con Docker levantado):
--   Get-Content postgres\reclasificar_categorias.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS respaldo_categorias_equipos AS
SELECT id, categoria, now() AS respaldado_en FROM equipos;

-- Propuesta por maquina (tabla temporal: desaparece al terminar la sesion).
CREATE TEMP TABLE propuesta_categorias AS
WITH base AS (
    SELECT id, codigo_activo, nombre, categoria AS actual,
           translate(lower(nombre), 'áéíóúüñ', 'aeiouun') AS n
    FROM equipos
)
SELECT id, codigo_activo, nombre, actual,
       CASE
           -- 6. Funcional y accesorios (primero: "cinta elastica" no es una cinta de correr)
           WHEN n ~ '(banda|elastic|resistencia|battle|cuerda|soga|plyo|cajon|caja de salto|trx|suspension|bosu|equilibrio|balance|foam|rodillo|colchoneta|fitball|balon suizo|pelota|escalera de agilidad|\yaro\y|slam ball|ab wheel|rueda abdominal|\ystep\y|funcional)'
               THEN 'funcional'
           -- 5. Bancos y soportes
           WHEN n ~ '(banco|bench|rack|jaula|smith|multipower|power tower|torre de|dominada|fondos|predicador|scott|soporte (para|de) |paralelas|hiperextension|silla romana)'
               THEN 'bancos_racks'
           -- 3. Carga de discos (antes que peso libre y placas: "prensa 45", "hack", "hammer"...)
           WHEN n ~ '(hammer|plate.?loaded|carga de disco|con disco|de discos|hack|prensa.*(45|inclin|disco)|(45|inclin).*prensa|hip.?thrust|empuje de cadera|articulad|pendulum|belt squat|t-?bar|trineo|\ysled\y|remo (con soporte|en t))'
               THEN 'discos'
           -- 1. Cardio
           WHEN n ~ '(cinta|trotadora|treadmill|bicicleta|bike|spinning|eliptic|remadora|rower|ergometro|maquina de remo|escalador|stairmaster|stepmill|skierg|ski erg|simulador de esqui|cardio|assault|arc trainer)'
               THEN 'cardio'
           -- 4. Peso libre
           WHEN n ~ '(mancuerna|dumbbell|barra|disco|bumper|kettlebell|pesa rusa|balon medicinal|medicine|pesas|mancuernero)'
               THEN 'peso_libre'
           -- 2. Placas / guiadas (selector de peso y poleas)
           WHEN n ~ '(extension|cuadriceps|curl|femoral|isquio|polea|jalon|pulldown|pec ?deck|mariposa|contractor|cruce|cable|crossover|abductor|aductor|gluteo|gemelo|pantorrilla|multiestacion|multigym|multifuncion|prensa|press|remo|torso|abdominal|dorsal|biceps|triceps|pullover|maquina)'
               THEN 'placas'
       END AS nueva
FROM base;

-- Aplica solo donde hay regla y cambia algo.
UPDATE equipos e
   SET categoria = p.nueva
  FROM propuesta_categorias p
 WHERE e.id = p.id AND p.nueva IS NOT NULL AND e.categoria IS DISTINCT FROM p.nueva;

COMMIT;

-- ---- Resultado ----------------------------------------------------------------

\echo
\echo '== Cambios realizados =='
SELECT codigo_activo, nombre, COALESCE(actual, '(vacia)') AS antes, nueva AS ahora
FROM propuesta_categorias
WHERE nueva IS NOT NULL AND actual IS DISTINCT FROM nueva
ORDER BY nueva, nombre;

\echo
\echo '== Maquinas por categoria =='
SELECT COALESCE(categoria, '(sin categoria)') AS categoria, COUNT(*) AS maquinas
FROM equipos GROUP BY 1 ORDER BY 1;

\echo
\echo '== SIN CLASIFICAR (corregir con el boton Editar del panel) =='
SELECT codigo_activo, nombre, COALESCE(categoria, '(vacia)') AS categoria_actual
FROM equipos
WHERE categoria IS NULL OR categoria NOT IN ('cardio', 'placas', 'discos', 'peso_libre', 'bancos_racks', 'funcional')
ORDER BY nombre;
