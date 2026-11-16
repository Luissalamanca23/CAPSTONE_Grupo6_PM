@echo off
rem Hace un respaldo de PostgreSQL y de MongoDB ahora mismo (ademas del automatico diario).
rem Los archivos quedan en respaldos\auto. Ver respaldo\LEEME.md.
cd /d "%~dp0"

echo ==^> Asegurando que los servicios de respaldo esten corriendo
docker compose up -d respaldo-postgres respaldo-mongo
if errorlevel 1 goto fallo

echo ==^> Respaldo de PostgreSQL
docker compose exec -T respaldo-postgres sh -c "tr -d '\r' < /scripts/respaldar.sh > /tmp/r.sh && sh /tmp/r.sh postgres una-vez"
if errorlevel 1 goto fallo

echo ==^> Respaldo de MongoDB
docker compose exec -T respaldo-mongo sh -c "tr -d '\r' < /scripts/respaldar.sh > /tmp/r.sh && sh /tmp/r.sh mongo una-vez"
if errorlevel 1 goto fallo

echo.
echo Listo. Los respaldos estan en la carpeta respaldos\auto.
pause
exit /b 0

:fallo
echo.
echo Algo fallo. Revisa el mensaje de arriba (el sistema debe estar levantado: docker compose up -d).
pause
exit /b 1
