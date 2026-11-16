#!/bin/sh
# Restauracion de los respaldos de GymKeep (RNF-21). Corre dentro de los servicios de respaldo.
#
#   restaurar.sh <postgres|mongo> prueba [archivo]   PRUEBA: restaura en una base temporal, mide el tiempo,
#                                                    compara los conteos con los del respaldo y borra la temporal.
#                                                    No toca los datos reales.
#   restaurar.sh <postgres|mongo> real   [archivo]   RESTAURACION REAL: pisa los datos actuales con el respaldo.
#                                                    Exige CONFIRMAR=SI en el entorno.
# Sin [archivo] usa el respaldo automatico mas reciente.
# Criterio RNF-21: restauracion en menos de 30 minutos y sin perdida respecto del ultimo respaldo.
set -u

TIPO="${1:-}"
MODO="${2:-}"
ARCHIVO="${3:-}"
DESTINO="${DESTINO:-/respaldos}"
MONGO_DB="${MONGO_DB:-gymkeep_ai}"
LIMITE_SEG=1800

case "$TIPO" in postgres|mongo) ;; *) echo "Uso: restaurar.sh postgres|mongo prueba|real [archivo]" >&2; exit 2 ;; esac
case "$MODO" in prueba|real) ;; *) echo "Uso: restaurar.sh postgres|mongo prueba|real [archivo]" >&2; exit 2 ;; esac

if [ "$TIPO" = "postgres" ]; then ext="dump"; else ext="archive.gz"; fi

if [ -z "$ARCHIVO" ]; then
  ARCHIVO=$(ls -1 "$DESTINO"/auto_${TIPO}_*."$ext" 2>/dev/null | sort | tail -1)
fi
case "$ARCHIVO" in /*) ;; *) [ -n "$ARCHIVO" ] && ARCHIVO="$DESTINO/$ARCHIVO" ;; esac
if [ -z "$ARCHIVO" ] || [ ! -s "$ARCHIVO" ]; then
  echo "No hay un respaldo $TIPO para restaurar en $DESTINO." >&2
  exit 1
fi
CONTEOS="${ARCHIVO%."$ext"}.conteos.txt"
echo "Respaldo: $(basename "$ARCHIVO")"

if [ "$MODO" = "real" ] && [ "${CONFIRMAR:-}" != "SI" ]; then
  echo "La restauracion real pisa los datos actuales. Repite con CONFIRMAR=SI para continuar." >&2
  exit 3
fi

contar_postgres() {
  for t in $(psql -d "$1" -At -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1"); do
    echo "$t $(psql -d "$1" -At -c "SELECT count(*) FROM \"$t\"")"
  done
}
contar_mongo() {
  mongosh "$MONGO_URL" --quiet --eval "const d=db.getSiblingDB('$1'); d.getCollectionNames().sort().forEach(n=>print(n+' '+d.getCollection(n).countDocuments({})))"
}

inicio=$(date +%s)
if [ "$TIPO" = "postgres" ]; then
  if [ "$MODO" = "prueba" ]; then
    BD="gymkeep_prueba_restauracion"
    dropdb --if-exists "$BD" && createdb "$BD" || exit 1
    pg_restore -d "$BD" --no-owner --no-privileges --exit-on-error "$ARCHIVO"
    estado=$?
  else
    BD="${PGDATABASE:-gymkeep}"
    pg_restore -d "$BD" --clean --if-exists --no-owner --no-privileges "$ARCHIVO"
    estado=$?
  fi
  fin=$(date +%s)
  [ "$estado" -eq 0 ] && contar_postgres "$BD" > /tmp/conteos_restaurados.txt
else
  if [ "$MODO" = "prueba" ]; then
    BD="${MONGO_DB}_prueba"
    # Sin indices en la prueba: asi el TTL de Mongo no borra datos antiguos mientras se compara.
    mongorestore --uri="$MONGO_URL" --archive="$ARCHIVO" --gzip --quiet --drop --noIndexRestore \
      --nsInclude="$MONGO_DB.*" --nsFrom="$MONGO_DB.*" --nsTo="$BD.*"
  else
    BD="$MONGO_DB"
    mongorestore --uri="$MONGO_URL" --archive="$ARCHIVO" --gzip --quiet --drop --nsInclude="$MONGO_DB.*"
  fi
  estado=$?
  fin=$(date +%s)
  [ "$estado" -eq 0 ] && contar_mongo "$BD" > /tmp/conteos_restaurados.txt
fi

seg=$(( fin - inicio ))
if [ "$estado" -ne 0 ]; then
  echo "FALLO la restauracion (codigo $estado)." >&2
  exit 1
fi

# Comparacion con lo que habia al hacer el respaldo.
if [ -f "$CONTEOS" ]; then
  if diff -q "$CONTEOS" /tmp/conteos_restaurados.txt > /dev/null 2>&1; then
    iguales="SI (todas las tablas/colecciones coinciden con el respaldo)"; perdida=0
  else
    iguales="NO, diferencias:"; perdida=1
  fi
else
  iguales="no hay archivo de conteos para comparar"; perdida=2
fi

if [ "$seg" -lt "$LIMITE_SEG" ]; then tiempo="CUMPLE (< 30 min)"; else tiempo="NO CUMPLE (>= 30 min)"; fi

informe="$DESTINO/prueba_restauracion_$TIPO.txt"
{
  echo "=== Restauracion $MODO de $TIPO - $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo "Respaldo usado : $(basename "$ARCHIVO")"
  echo "Tiempo         : $seg s -> $tiempo"
  echo "Sin perdida    : $iguales"
} | tee -a "$informe"
if [ "$perdida" -eq 1 ]; then
  diff "$CONTEOS" /tmp/conteos_restaurados.txt | tee -a "$informe"
fi
echo "Conteos restaurados:" | tee -a "$informe"
sed 's/^/  /' /tmp/conteos_restaurados.txt | tee -a "$informe"

if [ "$MODO" = "prueba" ]; then
  if [ "$TIPO" = "postgres" ]; then dropdb --if-exists "$BD"; else mongosh "$MONGO_URL" --quiet --eval "db.getSiblingDB('$BD').dropDatabase()" > /dev/null; fi
  echo "Base temporal $BD eliminada; los datos reales no se tocaron."
fi
[ "$perdida" -eq 1 ] && exit 1
[ "$seg" -ge "$LIMITE_SEG" ] && exit 1
exit 0
