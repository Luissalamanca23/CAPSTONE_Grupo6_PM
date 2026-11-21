#!/usr/bin/env bash
# Crea una cuenta de GymKeep (o restablece su clave) en el servidor. Equivale a crear-admin.bat.
# La clave se escribe sin que se vea en pantalla.
set -euo pipefail

DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
if [ -z "$($DOCKER ps --filter 'name=^gymkeep_api$' --filter 'status=running' -q)" ]; then
  echo "La API no esta corriendo. Levanta el sistema primero: bash raspberry-pi/instalar-raspberry.sh" >&2
  exit 1
fi

read -r -p "RUN (ej. 12.345.678-5): " RUN
read -r -p "Nombre completo: " NOMBRE
read -r -p "Rol: admin o tecnico (Enter = admin): " ROL
ROL="${ROL:-admin}"
case "$ROL" in admin|tecnico) ;; *) echo "El rol debe ser admin o tecnico." >&2; exit 1 ;; esac

# -it: la API pide la clave con getpass (no se ve al escribirla ni queda en el historial).
$DOCKER exec -it gymkeep_api python -m app.crear_usuario --run "$RUN" --nombre "$NOMBRE" --rol "$ROL"
echo "Listo. Ya puedes iniciar sesion en el panel con ese RUN y esa clave."
