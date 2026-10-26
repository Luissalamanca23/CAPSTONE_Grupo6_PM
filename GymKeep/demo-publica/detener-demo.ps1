# Deja de publicar la demo y apaga el sistema. Con -BorrarDatos tambien borra la base de datos.
param([switch]$BorrarDatos)
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
# Con el archivo de camaras se apaga todo (incluye al de la demo normal).
$Compose = Join-Path $PSScriptRoot 'docker-compose.vision.yml'

$ts = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $ts) {
    foreach ($ruta in @("$env:ProgramFiles\Tailscale\tailscale.exe", "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe")) {
        if (Test-Path $ruta) { $ts = $ruta; break }
    }
}
if ($ts) { Write-Host '==> Quitando la publicacion (Funnel)'; & $ts funnel reset }
Write-Host '==> Apagando el sistema'
if ($BorrarDatos) { & docker compose -f $Compose down -v; Remove-Item (Join-Path $PSScriptRoot '.datos-reales') -ErrorAction SilentlyContinue } else { & docker compose -f $Compose down }
Write-Host 'Listo.'
