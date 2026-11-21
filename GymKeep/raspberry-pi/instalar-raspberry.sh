#!/usr/bin/env bash
# Instala y levanta GymKeep en una Raspberry Pi 5 (ARM64, 8 GB). Guia: raspberry-pi/LEEME.md
#
#   bash raspberry-pi/instalar-raspberry.sh                       # sin camara: panel, API y bases
#   bash raspberry-pi/instalar-raspberry.sh --camara rtsp://usuario:clave@192.168.1.50:554/stream
#   bash raspberry-pi/instalar-raspberry.sh --video mi_video.mp4  # video puesto en vision/datos/
#
# Es seguro repetirlo: no pisa el .env ni los datos que ya existan.
set -euo pipefail
cd "$(dirname "$0")/.."

fallar() { echo "ERROR: $*" >&2; exit 1; }

FUENTE=""
CAMARA_CODIGO="CAM-01"
while [ $# -gt 0 ]; do
  case "$1" in
    --camara) FUENTE="$2"; shift 2 ;;
    --video) FUENTE="/app/datos/$2"; shift 2 ;;
    --codigo-camara) CAMARA_CODIGO="$2"; shift 2 ;;
    *) fallar "opcion desconocida: $1" ;;
  esac
done

# 1) Comprobaciones del equipo -------------------------------------------------------------
[ "$(uname -m)" = "aarch64" ] || fallar "hace falta un sistema de 64 bits (aarch64); este es $(uname -m). Instala Raspberry Pi OS de 64 bits."
MODELO="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo desconocido)"
echo "Equipo: $MODELO"
case "$MODELO" in
  *"Raspberry Pi 5"*) ;;
  *) echo "AVISO: no es una Raspberry Pi 5. MongoDB 7 exige ARMv8.2-A y una Pi 4 (o anterior) no la tiene: la base de eventos no arrancaria."
     read -r -p "¿Continuar de todos modos? [s/N] " r; [ "$r" = "s" ] || exit 1 ;;
esac
RAM_MB=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
echo "Memoria: ${RAM_MB} MB"
[ "$RAM_MB" -ge 3500 ] || fallar "se necesitan al menos 4 GB de RAM (recomendado 8 GB)."
[ -r /etc/os-release ] && . /etc/os-release
[ "${ID:-}" = "debian" ] || fallar "se esperaba Raspberry Pi OS de 64 bits (Debian); este sistema es '${ID:-desconocido}'."

# 2) Docker Engine y Compose (repositorio oficial de Docker para Debian) -------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Instalando Docker Engine..."
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl openssl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "Docker instalado. Si el siguiente paso falla por permisos, cierra la sesion, vuelve a entrar y repite el comando."
fi
command -v openssl >/dev/null 2>&1 || sudo apt-get install -y openssl
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
VER=$($DOCKER compose version --short 2>/dev/null || true)
[ -n "$VER" ] || fallar "no se encontro el plugin 'docker compose'."
echo "Docker Compose $VER"
[ "$(printf '%s\n2.24.0\n' "${VER#v}" | sort -V | head -n1)" = "2.24.0" ] || fallar "se necesita Docker Compose 2.24 o superior (docker-compose.prod.yml usa !override y !reset)."

# 2b) Arranque con el sistema (Docker queda habilitado; los contenedores tienen restart: unless-stopped)
sudo systemctl enable --now docker >/dev/null 2>&1 || true

# 3) Archivo .env con secretos propios (solo si no existe) ---------------------------------
if [ ! -f .env ]; then
  PIN="$(shuf -i 1000-9999 -n 1)"
  cat > .env <<EOF
# Generado por raspberry-pi/instalar-raspberry.sh. Guardalo: no se sube a git.
POSTGRES_PASSWORD=$(openssl rand -hex 16)
MONGO_ROOT_PASSWORD=$(openssl rand -hex 16)
VISION_PIPELINE_KEY=$(openssl rand -hex 24)
# PIN para editar zonas y parametros de vision en el panel.
VISION_PIN=${PIN}
FRONTEND_URL=http://$(hostname).local
VISION_CAMARA=${CAMARA_CODIGO}
VISION_FUENTE=${FUENTE}
EOF
  chmod 600 .env
  echo "Se creo .env con claves generadas. PIN de edicion de vision: ${PIN}"
elif [ -n "$FUENTE" ]; then
  echo "AVISO: .env ya existe; no se modifica. Edita VISION_FUENTE a mano si cambiaste la camara."
fi
FUENTE_ACTUAL="$(grep -E '^VISION_FUENTE=' .env | cut -d= -f2- || true)"

# 4) Levantar ------------------------------------------------------------------------------
COMPOSE="$DOCKER compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.rpi.yml"
if [ -n "$FUENTE_ACTUAL" ]; then
  echo "Construyendo y levantando todo (la primera vez tarda varios minutos: compila la web e instala PyTorch)..."
  $COMPOSE up -d --build
else
  echo "Sin camara configurada: se levanta todo menos la vision. Para agregarla despues: edita VISION_FUENTE en .env y repite este comando."
  $COMPOSE up -d --build db mongo api frontend respaldo-postgres respaldo-mongo
fi

echo
$COMPOSE ps
echo
echo "Listo. Panel: http://$(hostname).local  (o http://$(hostname -I | awk '{print $1}'))"
echo "Siguiente paso: crear la primera cuenta con  bash raspberry-pi/crear-admin.sh"
