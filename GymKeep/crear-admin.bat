@echo off
rem Crea una cuenta de GymKeep (o restablece la clave si el RUN ya existe).
rem La primera cuenta debe ser administrador. Pide los datos por pantalla; la clave no se muestra.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear-admin.ps1" %*
echo.
pause
