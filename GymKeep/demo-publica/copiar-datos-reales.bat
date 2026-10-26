@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0copiar-datos-reales.ps1" %*
echo.
pause
