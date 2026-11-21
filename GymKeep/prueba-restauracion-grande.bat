@echo off
rem PRUEBA DE RESTAURACION CON UNA BASE MAS GRANDE (RNF-21).
rem 1) Agrega datos de prueba a la base de DESARROLLO (la del docker compose de esta carpeta; no toca
rem    la demo publica ni sus datos reales): 3.000 equipos ZZPRUEBA-*, 300.000 sesiones de uso,
rem    30.000 mantenciones, 15.000 incidencias resueltas y 200.000 detecciones en MongoDB.
rem 2) Hace un respaldo, y 3) prueba la restauracion (limite 30 minutos, sin perdida).
rem 4) Borra los datos de prueba y 5) hace un respaldo limpio para que el ultimo respaldo no los tenga.
rem Los informes quedan en respaldos\auto\prueba_restauracion_*_grande.txt. Requiere el sistema levantado
rem (docker compose up -d) y las credenciales por defecto (usuario gymkeep); si cambiaste el .env, ajustalas.
cd /d "%~dp0"
set "PGU=%POSTGRES_USER%"
if "%PGU%"=="" set "PGU=gymkeep"
set "PGD=%POSTGRES_DB%"
if "%PGD%"=="" set "PGD=gymkeep"
set "MGU=%MONGO_ROOT_USER%"
if "%MGU%"=="" set "MGU=gymkeep"
set "MGP=%MONGO_ROOT_PASSWORD%"
if "%MGP%"=="" set "MGP=gymkeep_mongo_password"

echo Esto agrega datos de PRUEBA a la base de desarrollo y al terminar los borra.
set /p OK=Escribe SI para continuar: 
if /i not "%OK%"=="SI" exit /b 0

echo.
echo ==^> 0/6 Levantando PostgreSQL y MongoDB de desarrollo (si no estaban corriendo)
docker compose up -d db mongo
if errorlevel 1 goto fallo
set "N=0"
:espera_pg
docker compose exec -T db pg_isready -q -U %PGU% -d %PGD%
if not errorlevel 1 goto espera_mongo_ini
set /a N+=1
if %N% GEQ 30 (echo PostgreSQL no quedo listo en 60 s. & goto fallo)
timeout /t 2 /nobreak >nul
goto espera_pg
:espera_mongo_ini
set "N=0"
:espera_mongo
docker compose exec -T mongo mongosh -u %MGU% -p %MGP% --authenticationDatabase admin --quiet --eval "db.runCommand({ping:1}).ok" >nul 2>nul
if not errorlevel 1 goto listo
set /a N+=1
if %N% GEQ 30 (echo MongoDB no quedo listo en 60 s. & goto fallo)
timeout /t 2 /nobreak >nul
goto espera_mongo
:listo

echo ==^> Borrando restos de datos de prueba de un intento anterior (si los hay)
docker compose exec -T db psql -q -U %PGU% -d %PGD% -v ON_ERROR_STOP=1 < respaldo\carga_prueba_limpiar.sql >nul
if errorlevel 1 goto fallo
docker compose cp respaldo\carga_prueba_limpiar.js mongo:/tmp/carga_prueba_limpiar.js >nul 2>nul
docker compose exec -T mongo mongosh -u %MGU% -p %MGP% --authenticationDatabase admin --quiet gymkeep_ai --file /tmp/carga_prueba_limpiar.js
if errorlevel 1 goto fallo

echo.
echo ==^> 1/6 Cargando datos de prueba en PostgreSQL
docker compose exec -T db psql -q -U %PGU% -d %PGD% -v ON_ERROR_STOP=1 < respaldo\carga_prueba.sql
if errorlevel 1 goto fallo
echo ==^> 2/6 Cargando datos de prueba en MongoDB
docker compose cp respaldo\carga_prueba.js mongo:/tmp/carga_prueba.js
docker compose exec -T mongo mongosh -u %MGU% -p %MGP% --authenticationDatabase admin --quiet gymkeep_ai --file /tmp/carga_prueba.js
if errorlevel 1 goto fallo

echo.
echo ==^> 3/6 Respaldo con los datos grandes
docker compose up -d respaldo-postgres respaldo-mongo
rem Al arrancar, cada servicio hace su propio respaldo; se espera a que termine y a que cambie el minuto
rem para que no choque con el respaldo manual de abajo (el nombre lleva el minuto).
echo    Esperando 75 s a que terminen los respaldos automaticos de arranque...
timeout /t 75 /nobreak >nul
docker compose exec -T respaldo-postgres sh -c "tr -d '\r' < /scripts/respaldar.sh > /tmp/r.sh && sh /tmp/r.sh postgres una-vez"
if errorlevel 1 goto fallo
docker compose exec -T respaldo-mongo sh -c "tr -d '\r' < /scripts/respaldar.sh > /tmp/r.sh && sh /tmp/r.sh mongo una-vez"
if errorlevel 1 goto fallo
for %%F in (respaldos\auto\auto_postgres_*.dump) do echo    %%~nxF  %%~zF bytes

echo.
echo ==^> 4/6 Prueba de restauracion de PostgreSQL
docker compose exec -T respaldo-postgres sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh postgres prueba"
set RES_PG=%errorlevel%
echo.
echo ==^> 4/6 Prueba de restauracion de MongoDB
docker compose exec -T respaldo-mongo sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh mongo prueba"
set RES_MG=%errorlevel%
copy /y respaldos\auto\prueba_restauracion_postgres.txt respaldos\auto\prueba_restauracion_postgres_grande.txt >nul 2>nul
copy /y respaldos\auto\prueba_restauracion_mongo.txt respaldos\auto\prueba_restauracion_mongo_grande.txt >nul 2>nul

echo.
echo ==^> 5/6 Borrando los datos de prueba
docker compose exec -T db psql -q -U %PGU% -d %PGD% -v ON_ERROR_STOP=1 < respaldo\carga_prueba_limpiar.sql
docker compose cp respaldo\carga_prueba_limpiar.js mongo:/tmp/carga_prueba_limpiar.js
docker compose exec -T mongo mongosh -u %MGU% -p %MGP% --authenticationDatabase admin --quiet gymkeep_ai --file /tmp/carga_prueba_limpiar.js

echo.
echo ==^> 6/6 Respaldo limpio (para que el ultimo respaldo no tenga datos de prueba)
docker compose exec -T respaldo-postgres sh -c "tr -d '\r' < /scripts/respaldar.sh > /tmp/r.sh && sh /tmp/r.sh postgres una-vez"
docker compose exec -T respaldo-mongo sh -c "tr -d '\r' < /scripts/respaldar.sh > /tmp/r.sh && sh /tmp/r.sh mongo una-vez"

echo.
if "%RES_PG%"=="0" if "%RES_MG%"=="0" (
  echo RESULTADO: CUMPLE RNF-21 con la base grande - ambas restauraciones en menos de 30 min y sin perdida.
) else (
  echo RESULTADO: revisa lo de arriba - PostgreSQL=%RES_PG%  MongoDB=%RES_MG% (0 = bien^).
)
echo Informes: respaldos\auto\prueba_restauracion_postgres_grande.txt y prueba_restauracion_mongo_grande.txt
echo El respaldo grande queda en respaldos\auto (puedes borrarlo a mano si quieres liberar espacio).
pause
exit /b 0

:fallo
echo.
echo Algo fallo. Los datos de prueba pueden haber quedado cargados: para borrarlos ejecuta
echo   docker compose exec -T db psql -U %PGU% -d %PGD% ^< respaldo\carga_prueba_limpiar.sql
echo   docker compose cp respaldo\carga_prueba_limpiar.js mongo:/tmp/l.js ^&^& docker compose exec -T mongo mongosh -u %MGU% -p %MGP% --authenticationDatabase admin gymkeep_ai --file /tmp/l.js
pause
exit /b 1
