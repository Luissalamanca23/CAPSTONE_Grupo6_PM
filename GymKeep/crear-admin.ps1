# Crea una cuenta de GymKeep o restablece su clave. Funciona con el sistema real y con la demo
# (la API siempre se llama gymkeep_api). La clave se escribe sin que se vea en pantalla.
$ErrorActionPreference = 'Stop'

$corriendo = docker ps --filter 'name=^gymkeep_api$' --filter 'status=running' -q 2>$null
if (-not $corriendo) {
    Write-Host 'La API no esta corriendo. Levanta el sistema primero (docker compose up -d --build o iniciar-demo-real.bat).' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host 'Crear cuenta de GymKeep' -ForegroundColor Cyan
$run = Read-Host 'RUN (ej. 12.345.678-5)'
$nombre = Read-Host 'Nombre completo'
$rol = Read-Host 'Rol: admin o tecnico (Enter = admin)'
if (-not $rol) { $rol = 'admin' }
if ($rol -notin @('admin', 'tecnico')) {
    Write-Host 'El rol debe ser admin o tecnico.' -ForegroundColor Red
    exit 1
}

# -it: la API pide la clave con getpass (no se ve al escribirla ni queda en el historial).
docker exec -it gymkeep_api python -m app.crear_usuario --run "$run" --nombre "$nombre" --rol $rol
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host ''
Write-Host 'Listo. Ya puedes iniciar sesion en el panel con ese RUN y esa clave.' -ForegroundColor Green
