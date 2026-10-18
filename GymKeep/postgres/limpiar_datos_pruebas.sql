-- ============================================================================
-- limpiar_datos_pruebas.sql
--
-- Borra TODOS los datos de prueba para empezar con los datos de un gym real:
--   sucursales, zonas, equipos (maquinas), QR, camaras, incidencias (reportes),
--   mantenimientos, sesiones de uso, eventos IA y auditoria.
--
-- SE CONSERVA (catalogos, no son datos de prueba):
--   tipos_falla, modelos_ia, y la fila de "empresas" (renombrala abajo).
--
-- Los ids vuelven a empezar en 1 (RESTART IDENTITY).
-- ES IRREVERSIBLE: haz respaldo antes si hay algo que quieras conservar:
--   docker compose exec -T db pg_dump -U gymkeep gymkeep > respaldo.sql
--
-- Ejecutar (desde la carpeta GymKeep, con Docker levantado):
--   Get-Content postgres\limpiar_datos_pruebas.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
-- ============================================================================

BEGIN;

TRUNCATE TABLE
    registros_auditoria,
    eventos_ia_resumen,
    sesiones_uso,
    mantenimientos,
    incidencias,
    camara_equipos,
    qr_equipos,
    camaras,
    equipos,
    zonas,
    sucursales
RESTART IDENTITY;

-- Opcional: ponle el nombre de tu gimnasio a la empresa que queda.
-- (Descomenta y edita; el RUT es opcional.)
-- UPDATE empresas
--    SET razon_social = 'Nombre Legal SpA',
--        nombre_fantasia = 'Nombre del Gym',
--        rut = NULL,
--        email_contacto = 'contacto@migym.cl';

COMMIT;

-- Resultado: todo en 0 salvo catalogos y empresa.
SELECT 'empresas' AS tabla, COUNT(*) FROM empresas
UNION ALL SELECT 'sucursales', COUNT(*) FROM sucursales
UNION ALL SELECT 'equipos', COUNT(*) FROM equipos
UNION ALL SELECT 'incidencias', COUNT(*) FROM incidencias
UNION ALL SELECT 'camaras', COUNT(*) FROM camaras
UNION ALL SELECT 'tipos_falla (se conserva)', COUNT(*) FROM tipos_falla
UNION ALL SELECT 'modelos_ia (se conserva)', COUNT(*) FROM modelos_ia;
