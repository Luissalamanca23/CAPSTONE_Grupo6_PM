@echo off
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
set "VIDEO=datos\gym_completo_tramoA.mp4"
if not exist "%PY%" (
  echo No encuentro %PY%. Abre este archivo desde GymKeep\vision.
  pause
  exit /b 1
)
if not exist "%VIDEO%" (
  echo No encuentro %VIDEO%.
  pause
  exit /b 1
)
if not exist medicion_vision.py (
  copy "..\..\Fase 2\Evidencias Proyecto\documentos importantes\versiones actualizadas\medicion_vision.py" medicion_vision.py >nul
)
echo.
echo === Medicion del video 3 (tramo A) ===
echo Procesando con YOLO en CPU: puede tardar entre 10 y 40 minutos. No cierres esta ventana.
echo (La primera vez descarga el modelo yolo26s.pt, hace falta internet.)
echo.
"%PY%" -m gymkeep_vision procesar "%VIDEO%" -c config\video3.yaml --inicio 2026-11-21T10:00:00 --verdad conteo_video3.csv -o salida\video3_tramoA
if errorlevel 1 (
  echo.
  echo La corrida fallo. Copia el mensaje de arriba y mandamelo.
  pause
  exit /b 1
)
echo.
echo === Resultado frente al conteo manual ===
"%PY%" medicion_vision.py salida\video3_tramoA > resultado_video3.txt
type resultado_video3.txt
echo.
echo Listo. Los resultados quedaron en GymKeep\vision\resultado_video3.txt y GymKeep\vision\salida\video3_tramoA
pause
