#!/bin/sh
# Respaldo automatico de GymKeep (RNF-21). Corre dentro de los servicios `respaldo-postgres` y
# `respaldo-mongo` de docker-compose.yml.
#
#   respaldar.sh postgres          -> queda esperando y respalda todos los dias a HORA_UTC
#   respaldar.sh mongo             -> igual, para MongoDB
#   respaldar.sh postgres una-vez  -> hace un respaldo ahora mismo y termina
#
# Cada respaldo deja en /respaldos (carpeta respaldos/auto del proyecto):
#   auto_<tipo>_<AAAAMMDD_HHMM>.dump | .archive.gz   el respaldo
#   auto_<tipo>_<AAAAMMDD_HHMM>.conteos.txt           filas/documentos por tabla/coleccion al respaldar
#                                                     (la prueba de restauracion lo usa para comprobar que no se perdio nada)
#   ultimo_estado_<tipo>.txt                          OK o FALLO del ultimo intento, con la fecha
# Se conservan los ultimos RETENCION_DIAS dias; los mas antiguos se borran.
set -u

TIPO="${1:-}"
MODO="${2:-diario}"
DESTINO="${DESTINO:-/respaldos}"
HORA_UTC="${HORA_UTC:-06:00}"          # 06:00 UTC = 03:00 en Chile en horario de verano (02:00 en invierno)
RETENCION_DIAS="${RETENCION_DIAS:-7}"
MONGO_DB="${MONGO_DB:-gymkeep_ai}"

case "$TIPO" in
  postgres|mongo) ;;
  *) echo "Uso: respaldar.sh postgres|mongo [una-vez]" >&2; exit 2 ;;
esac

mkdir -p "$DESTINO"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] respaldo-$TIPO: $*"; }

sin_ceros() { v="$1"; v="${v#0}"; echo "${v:-0}"; }

# Segundos que faltan para la proxima vez que sean HH:MM UTC (si ya paso hoy, mañana).
segundos_hasta() {
  h=$(sin_ceros "${1%%:*}"); m=$(sin_ceros "${1##*:}")
  ah=$(sin_ceros "$(date -u +%H)"); am=$(sin_ceros "$(date -u +%M)"); as=$(sin_ceros "$(date -u +%S)")
  dif=$(( h * 3600 + m * 60 - (ah * 3600 + am * 60 + as) ))
  [ "$dif" -le 0 ] && dif=$(( dif + 86400 ))
  echo "$dif"
}

contar_postgres() {
  for t in $(psql -At -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"); do
    echo "$t $(psql -At -c "SELECT count(*) FROM \"$t\"")"
  done
}

contar_mongo() {
  mongosh "$MONGO_URL" --quiet --eval "const d=db.getSiblingDB('$MONGO_DB'); d.getCollectionNames().sort().forEach(n=>print(n+' '+d.getCollection(n).countDocuments({})))"
}

registrar_estado() {
  echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ) $2" > "$DESTINO/ultimo_estado_$TIPO.txt"
}

hacer_respaldo() {
  sello=$(date -u +%Y%m%d_%H%M)
  if [ "$TIPO" = "postgres" ]; then ext="dump"; else ext="archive.gz"; fi
  base="$DESTINO/auto_${TIPO}_${sello}"
  final="$base.$ext"
  tmp="$final.tmp"
  log "Iniciando respaldo -> $(basename "$final")"

  if [ "$TIPO" = "postgres" ]; then
    pg_dump -Fc -f "$tmp" && pg_restore -l "$tmp" > /dev/null
  else
    mongodump --uri="$MONGO_URL" --db="$MONGO_DB" --archive="$tmp" --gzip --quiet && gzip -t "$tmp"
  fi
  estado=$?

  if [ "$estado" -ne 0 ] || [ ! -s "$tmp" ]; then
    rm -f "$tmp"
    log "FALLO el respaldo (codigo $estado)"
    registrar_estado FALLO "no se pudo generar $(basename "$final")"
    return 1
  fi
  mv "$tmp" "$final"

  if [ "$TIPO" = "postgres" ]; then contar_postgres > "$base.conteos.txt"; else contar_mongo > "$base.conteos.txt"; fi
  tam=$(wc -c < "$final")
  log "OK: $(basename "$final") ($tam bytes)"
  registrar_estado OK "$(basename "$final") $tam bytes"

  # Retencion: borra los respaldos automaticos de este tipo con mas de RETENCION_DIAS dias.
  find "$DESTINO" -maxdepth 1 -name "auto_${TIPO}_*" -mtime +"$RETENCION_DIAS" -exec rm -f {} +
  return 0
}

if [ "$MODO" = "una-vez" ]; then
  hacer_respaldo
  exit $?
fi

log "Programado todos los dias a las $HORA_UTC UTC; se conservan $RETENCION_DIAS dias en $DESTINO"
# Si todavia no hay ningun respaldo (primer arranque), se hace uno de inmediato.
if ! ls "$DESTINO"/auto_${TIPO}_*.dump "$DESTINO"/auto_${TIPO}_*.archive.gz > /dev/null 2>&1; then
  hacer_respaldo
fi
while true; do
  espera=$(segundos_hasta "$HORA_UTC")
  log "Proximo respaldo en $espera s"
  sleep "$espera"
  hacer_respaldo
  sleep 61   # evita repetir el respaldo si el reloj quedo en la misma hora
done
