@echo off
rem Demo publica con TUS datos reales y el modulo de camaras. Antes: copiar-datos-reales.bat (una vez)
rem y poner tus videos en GymKeep\vision\datos\. Con los 3 videos de la medicion (cctv_cintas.mp4,
rem gym_fijo_1080.mp4.mp4 y gym_completo_tramoA.mp4) levanta 3 camaras, una por video, con sus zonas.
rem Una sola camara (pregunta cual video):  iniciar-demo-real.bat -UnaCamara
rem Otro video o camara:  iniciar-demo-real.bat -Video mi_video.mp4 -Camara CAM-01
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-demo.ps1" -DatosReales -Camaras %*
echo.
pause
