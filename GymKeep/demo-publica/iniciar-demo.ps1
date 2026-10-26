# Levanta GymKeep (base de datos + API + web) y lo publica en internet con Tailscale Funnel.
# Uso: doble clic en iniciar-demo.bat  (o:  .\iniciar-demo.ps1 [-SinDatosDemo] [-SinSimulacion])
#   -DatosReales  no carga datos de ejemplo ni simula uso (para la copia hecha con
#                 copiar-datos-reales.bat; se activa solo si existe el archivo .datos-reales)
#   -Camaras      agrega el modulo de vision: analiza un video de ..\vision\datos como camara en vivo
#   -Video        nombre del video (si no, pregunta cual); -Camara codigo de la camara (CAM-01)
# Requisitos: Docker Desktop abierto y Tailscale instalado con la sesion iniciada.
param([switch]$SinDatosDemo, [switch]$SinSimulacion, [switch]$DatosReales, [switch]$Camaras, [string]$Video = '', [string]$Camara = 'CAM-01')

$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
# Registro del ultimo arranque (para revisar si algo falla): ultimo-arranque.log
try { Start-Transcript -Path (Join-Path $PSScriptRoot 'ultimo-arranque.log') -Force | Out-Null } catch { }
$Puerto = if ($env:DEMO_PORT) { $env:DEMO_PORT } else { '8088' }
$Compose = Join-Path $PSScriptRoot 'docker-compose.yml'
if ($Camaras) { $Compose = Join-Path $PSScriptRoot 'docker-compose.vision.yml' }
$MarcaReales = Join-Path $PSScriptRoot '.datos-reales'
if ($DatosReales -or (Test-Path $MarcaReales)) {
    # Datos reales copiados a la demo: NUNCA cargar datos de ejemplo ni simular uso (borraria sesiones reales).
    $DatosReales = $true; $SinDatosDemo = $true; $SinSimulacion = $true
}
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

# ---- 2b. Camaras: elegir el video y proteger la edicion ----
if ($Camaras) {
    Paso 'Preparando las camaras'
    $DatosVideo = Join-Path (Split-Path $PSScriptRoot -Parent) 'vision\datos'
    $ext = '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.webm'
    $videos = @(Get-ChildItem $DatosVideo -File -ErrorAction SilentlyContinue |
        Where-Object { $ext -contains $_.Extension.ToLower() -and $_.Name -notlike '_*' } |
        Sort-Object LastWriteTime -Descending)
    if ($videos.Count -eq 0) { Fallo "No hay videos en $DatosVideo . Copia ahi tu video (mp4, mov, avi, mkv) y vuelve a ejecutar." }
    $elegido = $null
    if ($Video) {
        $elegido = $videos | Where-Object { $_.Name -ieq $Video } | Select-Object -First 1
        if (-not $elegido) { Fallo "No encuentro '$Video' en $DatosVideo ." }
    } elseif ($videos.Count -eq 1) {
        $elegido = $videos[0]
    } else {
        Write-Host '    Videos disponibles (el mas nuevo primero):'
        for ($i = 0; $i -lt $videos.Count; $i++) {
            $mb = [math]::Round($videos[$i].Length / 1MB)
            Write-Host ('      [{0}] {1}  ({2} MB, {3:dd-MM HH:mm})' -f ($i + 1), $videos[$i].Name, $mb, $videos[$i].LastWriteTime)
        }
        $resp = Read-Host '    Numero del video a usar (Enter = el [1])'
        $n = 1
        if ($resp -match '^\d+$') { $n = [int]$resp }
        if ($n -lt 1 -or $n -gt $videos.Count) { Fallo 'Numero de video no valido.' }
        $elegido = $videos[$n - 1]
    }
    Write-Host "    Video: $($elegido.Name)   Camara: $Camara"
    $env:VISION_FUENTE = "/app/datos/$($elegido.Name)"
    $env:VISION_CAMARA = $Camara
    # La demo esta en internet: editar zonas/parametros pide PIN y el pipeline manda una clave.
    if (-not $env:VISION_PIN) { $env:VISION_PIN = (Get-Random -Minimum 100000 -Maximum 999999).ToString() }
    if (-not $env:VISION_PIPELINE_KEY) { $env:VISION_PIPELINE_KEY = -join ((1..24) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }) }
}

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

if ($Camaras) {
    $codigos = @((DC exec -T db psql -U $PgUser -d $PgDb -tAc 'select codigo from camaras order by id') | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    if ($codigos -notcontains $Camara) {
        if ($codigos.Count -eq 1) {
            Write-Host "    La camara '$Camara' no existe; uso la unica camara de la base: $($codigos[0])" -ForegroundColor Yellow
            $Camara = $codigos[0]
            $env:VISION_CAMARA = $Camara
            DC up -d vision
        } else {
            Write-Host "    [!] La camara '$Camara' no existe en la base (hay: $($codigos -join ', ')). Ejecuta con -Camara <codigo> o crea una en el panel (Camaras > Agregar camara)." -ForegroundColor Yellow
        }
    }
}

# ---- 4. Datos de demostracion (una sola vez) ----
if (-not $SinDatosDemo) {
    $n = [int]((DC exec -T db psql -U $PgUser -d $PgDb -tAc 'select count(*) from incidencias') | Select-Object -First 1)
    if ($n -ge 100) {
        Write-Host '    Los datos de demostracion ya estaban cargados.'
    } else {
        Paso 'Cargando datos de demostracion (unos segundos)'
        # El orden importa: historial_demo.sql borra lo que genera datos_demo_dashboard.sql, por eso
        # va antes; ajustar-datos-demo.sql reparte las fechas de los reportes antes del dashboard.
        $scripts = @(
            @{ Archivo = 'reset_demo_incidencias.sql'; Carpeta = $Postgres },
            @{ Archivo = 'agregar_mas_datos.sql'; Carpeta = $Postgres },
            @{ Archivo = 'reclasificar_categorias.sql'; Carpeta = $Postgres },
            @{ Archivo = 'historial_demo.sql'; Carpeta = $Postgres },
            @{ Archivo = 'ajustar-datos-demo.sql'; Carpeta = $PSScriptRoot },
            @{ Archivo = 'datos_demo_dashboard.sql'; Carpeta = $Postgres }
        )
        foreach ($sc in $scripts) {
            $f = $sc.Archivo
            Write-Host "    $f"
            DC cp (Join-Path $sc.Carpeta $f) "db:/tmp/$f"
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
if ($Camaras) {
    Write-Host "   Camaras:                       $UrlPublica/camaras"
    Write-Host "   PIN para editar zonas/parametros: $($env:VISION_PIN)   (no lo compartas)"
    Write-Host '   La primera vez el pipeline tarda 1-2 minutos en mostrar la imagen. Si no aparece:'
    Write-Host "     docker compose -f `"$Compose`" logs --tail 30 vision"
}
if ($DatosReales) { Write-Host '   (Datos REALES: cualquiera con el enlace puede verlos y editarlos; apaga al terminar)' -ForegroundColor Yellow }
Write-Host ' Para apagar todo: detener-demo.bat'
Write-Host '=====================================================' -ForegroundColor Green
Write-Host 'La primera vez la direccion puede tardar 1-2 minutos en abrir desde un celular.'
