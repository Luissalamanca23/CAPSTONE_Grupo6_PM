@echo off
rem Demo publica con TUS datos reales y el modulo de camaras. Antes: copiar-datos-reales.bat (una vez)
rem y poner tu video en GymKeep\vision\datos\. Si hay varios videos, pregunta cual usar.
rem Para otro video o camara:  iniciar-demo-real.bat -Video mi_video.mp4 -Camara CAM-01
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-demo.ps1" -DatosReales -Camaras %*
echo.
pause
