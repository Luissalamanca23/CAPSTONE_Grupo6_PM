@echo off
rem Apaga la demo y levanta el sistema normal (tus datos reales: volumenes gymkeep_*).
rem No borra ningun dato: "down" sin -v conserva todos los volumenes.
cd /d "%~dp0"

echo ==^> Dejando de publicar la demo (si estaba publicada)
if exist "%ProgramFiles%\Tailscale\tailscale.exe" "%ProgramFiles%\Tailscale\tailscale.exe" funnel reset

echo ==^> Apagando la demo (sus datos de prueba se conservan aparte)
docker compose -f demo-publica\docker-compose.vision.yml down

echo ==^> Levantando GymKeep con tus datos reales (incluye la foto opcional en el reporte)
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo Algo fallo al levantar el sistema. Revisa el mensaje de arriba.
  pause
  exit /b 1
)

echo ==^> Abriendo el panel
start "GymKeep panel" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Listo. Panel: http://localhost:5173   API: http://localhost:8000/docs
pause
