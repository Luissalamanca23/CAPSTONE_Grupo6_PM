@echo off
rem Igual que iniciar-demo-real.bat pero usa directamente el video de prueba cctv_cintas.mp4
rem (sin preguntar). Para tu video: iniciar-demo-real.bat
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-demo.ps1" -DatosReales -Camaras -Video cctv_cintas.mp4 %*
echo.
pause
