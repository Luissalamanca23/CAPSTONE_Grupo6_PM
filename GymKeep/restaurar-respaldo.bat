@echo off
rem RESTAURACION REAL: reemplaza los datos actuales por los del ultimo respaldo automatico.
rem Solo para emergencias (datos perdidos o danados). Para solo probar, usa probar-restauracion.bat.
cd /d "%~dp0"

echo ATENCION: esto reemplaza TODOS los datos actuales de PostgreSQL y MongoDB por los del ultimo respaldo.
echo Lo que se haya registrado despues de ese respaldo se perdera.
set /p CONF=Escribe SI para continuar: 
if /i not "%CONF%"=="SI" (
  echo Cancelado, no se cambio nada.
  pause
  exit /b 1
)

echo ==^> Deteniendo la API mientras se restaura
docker compose stop api

echo ==^> Restaurando PostgreSQL
docker compose exec -T -e CONFIRMAR=SI respaldo-postgres sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh postgres real"
echo ==^> Restaurando MongoDB
docker compose exec -T -e CONFIRMAR=SI respaldo-mongo sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh mongo real"

echo ==^> Levantando la API de nuevo
docker compose start api
echo.
echo Listo. Revisa los conteos de arriba y entra al panel para confirmar.
pause
