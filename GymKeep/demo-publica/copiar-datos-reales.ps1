# Copia tus datos REALES (volumenes gymkeep_*: base de datos, fotos y camaras) a la demo
# (volumenes gymkeep-demo_*). Los datos originales NO se modifican: solo se leen.
# Tambien deja un respaldo en ..\respaldos\ (no se sube a git).
# Uso: doble clic en copiar-datos-reales.bat. Despues: iniciar-demo-real.bat
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$Raiz = Split-Path $PSScriptRoot -Parent
$ComposeReal = Join-Path $Raiz 'docker-compose.yml'
$ComposeDemo = Join-Path $PSScriptRoot 'docker-compose.vision.yml'
$Resp = Join-Path $Raiz 'respaldos'
$PgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'gymkeep' }
$PgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'gymkeep' }
$MgUser = if ($env:MONGO_ROOT_USER) { $env:MONGO_ROOT_USER } else { 'gymkeep' }
$MgPass = if ($env:MONGO_ROOT_PASSWORD) { $env:MONGO_ROOT_PASSWORD } else { 'gymkeep_mongo_password' }
$MgDb = if ($env:MONGO_DB) { $env:MONGO_DB } else { 'gymkeep_ai' }
$Sello = Get-Date -Format 'yyyyMMdd_HHmm'

function Paso($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Fallo($m) { Write-Host "`n[X] $m" -ForegroundColor Red; exit 1 }
function Real { & docker compose -p gymkeep -f $ComposeReal @args }
function Demo { & docker compose -f $ComposeDemo @args }
function Esperar($contenedor) {
    for ($i = 0; $i -lt 60; $i++) {
        $e = (& docker inspect -f '{{.State.Health.Status}}' $contenedor 2>$null)
        if ($e -eq 'healthy') { return }
        Start-Sleep -Seconds 2
    }
    Fallo "$contenedor no quedo listo en 2 minutos."
}
function Cuenta($tabla) {
    $n = (& docker exec gymkeep_db psql -U $PgUser -d $PgDb -tAc "select count(*) from $tabla") | Select-Object -First 1
    return "$n".Trim()
}

Paso 'Revisando Docker'
$null = & docker info 2>&1
if ($LASTEXITCODE -ne 0) { Fallo 'Docker no esta corriendo. Abre Docker Desktop y vuelve a ejecutar.' }
New-Item -ItemType Directory -Force -Path $Resp | Out-Null

Paso 'Apagando la demo y el sistema normal (los datos NO se borran)'
Demo down
Real down

Paso 'Leyendo tus datos reales'
Real up -d db mongo
if ($LASTEXITCODE -ne 0) { Fallo 'No se pudo iniciar la base de datos real.' }
Esperar 'gymkeep_db'; Esperar 'gymkeep_mongo'
$real = @{}
foreach ($t in 'equipos', 'incidencias', 'mantenimientos', 'sesiones_uso', 'camaras') { $real[$t] = Cuenta $t }
Write-Host ("    Real: {0} equipos, {1} incidencias, {2} mantenimientos, {3} sesiones de uso, {4} camaras" -f $real.equipos, $real.incidencias, $real.mantenimientos, $real.sesiones_uso, $real.camaras)
if ([int]$real.equipos -eq 0) { Fallo 'La base real no tiene equipos: no copio nada para no pisar la demo con una base vacia.' }

Paso 'Haciendo el respaldo (PostgreSQL y MongoDB)'
$dumpPg = Join-Path $Resp "real_postgres_$Sello.dump"
$dumpMg = Join-Path $Resp "real_mongo_$Sello.archive"
& docker exec gymkeep_db pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/real.dump
if ($LASTEXITCODE -ne 0) { Fallo 'pg_dump fallo.' }
& docker cp gymkeep_db:/tmp/real.dump $dumpPg
& docker exec gymkeep_mongo mongodump --quiet --username $MgUser --password $MgPass --authenticationDatabase admin --db $MgDb --archive=/tmp/real.archive --gzip
if ($LASTEXITCODE -ne 0) { Fallo 'mongodump fallo.' }
& docker cp gymkeep_mongo:/tmp/real.archive $dumpMg
if (-not (Test-Path $dumpPg) -or (Get-Item $dumpPg).Length -lt 1000) { Fallo 'El respaldo de PostgreSQL quedo vacio.' }
if (-not (Test-Path $dumpMg) -or (Get-Item $dumpMg).Length -lt 100) { Fallo 'El respaldo de MongoDB quedo vacio.' }
Write-Host "    Respaldos en: $Resp"

Paso 'Apagando el sistema real'
Real down

Paso 'Cargando la copia en la demo (reemplaza los datos de ejemplo de la demo)'
Demo up -d db mongo
if ($LASTEXITCODE -ne 0) { Fallo 'No se pudo iniciar la base de la demo.' }
Esperar 'gymkeep_db'; Esperar 'gymkeep_mongo'
& docker cp $dumpPg gymkeep_db:/tmp/real.dump
& docker exec gymkeep_db psql -q -U $PgUser -d $PgDb -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
if ($LASTEXITCODE -ne 0) { Fallo 'No se pudo limpiar la base de la demo.' }
& docker exec gymkeep_db pg_restore -U $PgUser -d $PgDb --no-owner --no-privileges /tmp/real.dump
& docker cp $dumpMg gymkeep_mongo:/tmp/real.archive
& docker exec gymkeep_mongo mongorestore --quiet --username $MgUser --password $MgPass --authenticationDatabase admin --archive=/tmp/real.archive --gzip --drop --nsInclude "$MgDb.*"
if ($LASTEXITCODE -ne 0) { Fallo 'mongorestore fallo.' }

Paso 'Verificando la copia'
$ok = $true
foreach ($t in 'equipos', 'incidencias', 'mantenimientos', 'sesiones_uso', 'camaras') {
    $d = Cuenta $t
    $marca = if ($d -eq $real[$t]) { 'OK ' } else { 'DIF'; $ok = $false }
    Write-Host ("    [{0}] {1}: real {2} / demo {3}" -f $marca, $t, $real[$t], $d)
}
if (-not $ok) { Fallo 'Los conteos no coinciden. No marco la demo como "datos reales"; revisa los mensajes de arriba.' }

Paso 'Apagando la demo (queda lista para iniciar)'
Demo down
Set-Content -Path (Join-Path $PSScriptRoot '.datos-reales') -Value "copiado $Sello"

Write-Host "`n=====================================================" -ForegroundColor Green
Write-Host ' Listo: la demo ya tiene tus datos reales.' -ForegroundColor Green
Write-Host '   Siguiente paso: iniciar-demo-real.bat  (con camaras)'
Write-Host '   La demo con datos reales NO carga datos de ejemplo ni simula uso.'
Write-Host '   Tus datos originales siguen intactos (volver-a-datos-reales.bat).'
Write-Host '=====================================================' -ForegroundColor Green
