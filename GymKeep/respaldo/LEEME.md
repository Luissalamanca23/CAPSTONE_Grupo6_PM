# Respaldo automático y restauración (RNF-21)

Requisito: respaldo diario de PostgreSQL y MongoDB; restauración de prueba en menos de 30 minutos y sin pérdida respecto del último respaldo.

## Cómo funciona

`docker compose up -d` levanta dos servicios además del sistema:

- `respaldo-postgres`: cada día a las 06:00 UTC (03:00 en Chile en verano) ejecuta `pg_dump` y guarda `auto_postgres_AAAAMMDD_HHMM.dump`.
- `respaldo-mongo`: a la misma hora ejecuta `mongodump` y guarda `auto_mongo_AAAAMMDD_HHMM.archive.gz`.

Todo queda en la carpeta `respaldos\auto` del proyecto (ya está excluida de git). Junto a cada respaldo se guarda un `.conteos.txt` con las filas de cada tabla y los documentos de cada colección en ese momento, y `ultimo_estado_postgres.txt` / `ultimo_estado_mongo.txt` dicen si el último intento terminó en OK o FALLO. Se conservan los últimos 7 días. La primera vez que arrancan, si no hay ningún respaldo, hacen uno de inmediato.

Hora y días se cambian en el `.env` con `RESPALDO_HORA_UTC` y `RESPALDO_RETENCION_DIAS`.

El computador (o el servidor) tiene que estar encendido a esa hora: si está apagado, el respaldo de ese día no se hace. Docker retoma el horario al volver a encender.

## Hacer un respaldo ahora

Doble clic en `respaldar-ahora.bat`.

## Prueba de restauración (la evidencia del RNF-21)

Doble clic en `probar-restauracion.bat`. Para cada base:

1. Restaura el último respaldo en una base temporal (`gymkeep_prueba_restauracion` / `gymkeep_ai_prueba`), sin tocar los datos reales.
2. Mide el tiempo y lo compara con el límite de 30 minutos.
3. Compara las filas y los documentos restaurados con los que había al respaldar (sin pérdida).
4. Borra la base temporal y deja el informe en `respaldos\auto\prueba_restauracion_postgres.txt` y `prueba_restauracion_mongo.txt`.

Al final imprime `RESULTADO: CUMPLE RNF-21` si las dos bases cumplen. Ese informe y una captura de la ventana son lo que se pone como evidencia.

## Restauración real (emergencia)

`restaurar-respaldo.bat` pide escribir SI, detiene la API, reemplaza los datos actuales por los del último respaldo y vuelve a levantar la API. Todo lo registrado después de ese respaldo se pierde.

Para usar un respaldo en particular, en vez del último:

```
docker compose exec -T -e CONFIRMAR=SI respaldo-postgres sh -c "tr -d '\r' < /scripts/restaurar.sh > /tmp/r.sh && sh /tmp/r.sh postgres real auto_postgres_20261114_0600.dump"
```

## Límites

- La demo pública (`demo-publica`) tiene sus propias bases y no está incluida: son datos de prueba.
- Los respaldos viven en el mismo computador que los datos. Para protegerse de un disco dañado hay que copiar la carpeta `respaldos\auto` a un disco externo o a la nube de vez en cuando.
- MongoDB guarda solo `gymkeep_ai` (eventos, detecciones y telemetría de cámaras); las colecciones con vencimiento (TTL) se respaldan como estén ese día.
