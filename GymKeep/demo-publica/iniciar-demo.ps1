# Levanta GymKeep (base de datos + API + web) y lo publica en internet con Tailscale Funnel.
# Uso: doble clic en iniciar-demo.bat  (o:  .\iniciar-demo.ps1 [-SinDatosDemo] [-SinSimulacion])
# Requisitos: Docker Desktop abierto y Tailscale instalado con la sesion iniciada.
param([switch]$SinDatosDemo, [switch]$SinSimulacion)

$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$Puerto = if ($env:DEMO_PORT) { $env:DEMO_PORT } else { '8088' }
$Compose = Join-Path $PSScriptRoot 'docker-compose.yml'
$Postgres = Join-Path (Split-Path $PSScriptRoot -Parent) 'postgres'
$PgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'gymkeep' }
$PgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'gymkeep' }

function Paso($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Fallo($m) { Write-Host "`n[X] $m" -ForegroundColor Red; exit 1 }
function DC { & docker compose -f $Compose @args }

# ---- 1. Docker ----
Paso 'Revisando Docker'
$null = & docker info 2>&1
if ($LASTEXITCODE -ne 0) { Fallo 'Docker no esta corriendo. Abre Docker Desktop, espera a que diga "running" y vuelve a ejecutar.' }
$ver = (& docker compose version --short 2>$null)
if ($ver -match '^v?(\d+)\.(\d+)') {
    if ([int]$Matches[1] -lt 2 -or ([int]$Matches[1] -eq 2 -and [int]$Matches[2] -lt 20)) {
        Fallo "Docker Compose $ver es muy antiguo (se necesita 2.20 o superior). Actualiza Docker Desktop."
    }
}

# ---- 2. Tailscale ----
Paso 'Revisando Tailscale'
$ts = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $ts) {
    foreach ($ruta in @("$env:ProgramFiles\Tailscale\tailscale.exe", "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe")) {
        if (Test-Path $ruta) { $ts = $ruta; break }
    }
}
if (-not $ts) { Fallo 'No encuentro Tailscale. Instalalo desde https://tailscale.com/download e inicia sesion.' }
$estado = (& $ts status --json 2>$null) -join "`n" | ConvertFrom-Json
if (-not $estado -or $estado.BackendState -ne 'Running') {
    Fallo 'Tailscale no esta conectado. Abre Tailscale (icono junto al reloj), inicia sesion / pulsa Connect y vuelve a ejecutar.'
}
$host_ts = ([string]$estado.Self.DNSName).TrimEnd('.')
if (-not $host_ts -or -not $estado.CertDomains) {
    Fallo ("Falta activar MagicDNS y los certificados HTTPS en tu cuenta de Tailscale.`n" +
           "    Entra a https://login.tailscale.com/admin/dns , activa MagicDNS y pulsa 'Enable HTTPS'.`n" +
           "    Despues vuelve a ejecutar este script.")
}
$UrlPublica = "https://$host_ts"
Write-Host "    Direccion publica: $UrlPublica"

# ---- 3. Sistema ----
Paso 'Levantando base de datos, API y web (la primera vez tarda varios minutos)'
$env:FRONTEND_URL = $UrlPublica   # los QR llevan esta direccion
DC up -d --build
if ($LASTEXITCODE -ne 0) { Fallo 'docker compose no pudo levantar el sistema (revisa el mensaje de arriba).' }

Paso 'Esperando a que responda'
$listo = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Puerto/api/v1/equipamiento/?limit=1" -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $listo = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $listo) { Fallo "El sistema no respondio en 3 minutos. Mira los registros con:  docker compose -f `"$Compose`" logs --tail 50" }

# ---- 4. Datos de demostracion (una sola vez) ----
if (-not $SinDatosDemo) {
    $n = [int]((DC exec -T db psql -U $PgUser -d $PgDb -tAc 'select count(*) from incidencias') | Select-Object -First 1)
    if ($n -ge 100) {
        Write-Host '    Los datos de demostracion ya estaban cargados.'
    } else {
        Paso 'Cargando datos de demostracion (unos segundos)'
        foreach ($f in 'reset_demo_incidencias.sql', 'agregar_mas_datos.sql', 'datos_demo_dashboard.sql', 'historial_demo.sql') {
            Write-Host "    $f"
            DC cp (Join-Path $Postgres $f) "db:/tmp/$f"
            DC exec -T db psql -q -U $PgUser -d $PgDb -v ON_ERROR_STOP=1 -f "/tmp/$f" | Out-Null
            if ($LASTEXITCODE -ne 0) { Fallo "Fallo al cargar $f" }
        }
    }
}

# ---- 4b. Simulacion de uso real (en cada arranque) ----
# Borra TODAS las sesiones de uso de la base y genera sesiones nuevas hasta este momento,
# con el horario y los problemas de un gimnasio real (ver simular-uso-real.sql).
if (-not $SinSimulacion) {
    Paso 'Simulando el uso del gimnasio (borra las sesiones anteriores y crea sesiones nuevas)'
    DC cp (Join-Path $PSScriptRoot 'simular-uso-real.sql') 'db:/tmp/simular-uso-real.sql'
    DC exec -T db psql -q -U $PgUser -d $PgDb -v ON_ERROR_STOP=1 -f /tmp/simular-uso-real.sql
    if ($LASTEXITCODE -ne 0) { Fallo 'Fallo la simulacion de uso (revisa el mensaje de arriba).' }
}

# ---- 5. Publicar ----
Paso 'Publicando con Tailscale Funnel'
Write-Host '    (si es la primera vez, Tailscale muestra un enlace para habilitar Funnel: abrelo, aceptalo y espera)'
& $ts funnel --bg $Puerto
if ($LASTEXITCODE -ne 0) { Fallo 'Tailscale Funnel no se pudo activar. Revisa el mensaje de arriba.' }

Write-Host "`n=====================================================" -ForegroundColor Green
Write-Host ' GymKeep esta publicado' -ForegroundColor Green
Write-Host "   Web (cualquier celular o PC):  $UrlPublica"
Write-Host "   QR de una maquina:             $UrlPublica/api/v1/equipamiento/<id>/codigo-qr"
Write-Host '   (tambien en la web: Equipos > Ver detalle)'
Write-Host ' Para apagar todo: detener-demo.bat'
Write-Host '=====================================================' -ForegroundColor Green
Write-Host 'La primera vez la direccion puede tardar 1-2 minutos en abrir desde un celular.'
