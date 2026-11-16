@echo off
rem PRUEBA DE RESTAURACION (RNF-21): restaura el ultimo respaldo de PostgreSQL y de MongoDB en bases
rem temporales, mide cuanto demora (limite: 30 minutos), compara los conteos con los del respaldo
rem (sin perdida) y borra las bases temporales. No toca tus datos reales.
rem Deja el informe en respaldos\auto\prueba_restauracion_postgres.txt y ..._mongo.txt.
cd /d "%~dp0"

echo ==^> Prueba de restauracion de PostgreSQL
docker compose exec -T respaldo-postgres sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh postgres prueba"
set RES_PG=%errorlevel%

echo.
echo ==^> Prueba de restauracion de MongoDB
docker compose exec -T respaldo-mongo sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh mongo prueba"
set RES_MG=%errorlevel%

echo.
if "%RES_PG%"=="0" if "%RES_MG%"=="0" (
  echo RESULTADO: CUMPLE RNF-21 - ambas restauraciones en menos de 30 min y sin perdida.
) else (
  echo RESULTADO: revisa lo de arriba - PostgreSQL=%RES_PG%  MongoDB=%RES_MG% (0 = bien^).
)
echo Informes guardados en respaldos\auto.
pause
