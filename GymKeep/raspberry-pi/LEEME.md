# GymKeep en una Raspberry Pi 5 (8 GB)

Guía para dejar GymKeep funcionando en un servidor local de la sede: panel web, API, PostgreSQL,
MongoDB, respaldos automáticos y el módulo de visión, todo en una sola Raspberry Pi 5 de 8 GB.
El video no sale del gimnasio: se procesa en la propia Pi.

> **Estado de validación.** La combinación de archivos Compose se validó con `docker compose config` y los
> scripts con revisión de sintaxis. El instalador y el arranque completo **no se ejecutaron todavía de punta a
> punta en una Raspberry Pi 5**: la primera instalación real debe revisarse con `docker compose ps`, los
> registros de cada servicio y `medir_raspberry.py` (sección 6).

## 1. Qué se necesita

| Pieza | Requisito | Por qué |
|---|---|---|
| Equipo | Raspberry Pi **5** de 4 u 8 GB (recomendado 8 GB) | MongoDB 7 exige un procesador ARMv8.2-A: lo tiene la Pi 5 (Cortex-A76), **no** una Pi 4 ni anterior, donde la base de eventos no arranca |
| Sistema | Raspberry Pi OS **de 64 bits** (Debian), con `aarch64` | Las imágenes de PostgreSQL, MongoDB, nginx y PyTorch para ARM64 no existen en 32 bits |
| Alimentación | Fuente oficial USB-C de 27 W (5 V / 5 A) | La Pi 5 puede consumir hasta 5 A a 5 V; una fuente más débil provoca caídas de rendimiento o reinicios |
| Enfriamiento | Enfriador activo oficial (Active Cooler) o caja con ventilador | Toda Raspberry Pi empieza a limitar el procesador a los 80 °C y lo limita aún más a los 85 °C; la visión mantiene la CPU ocupada de forma continua |
| Almacenamiento | NVMe por la placa PCIe (recomendado) o microSD de 32 GB o más clase A2 | Las bases escriben todo el tiempo; una microSD común se desgasta antes |
| Red | Cable Ethernet y cámara IP con flujo RTSP | Una cámara por flujo `rtsp://usuario:clave@ip:554/ruta`, en la red local de la sede |

## 2. Preparar el equipo (una sola vez)

1. Instala **Raspberry Pi OS (64 bits)** con *Raspberry Pi Imager*. En las opciones avanzadas fija
   el nombre del equipo (por ejemplo `gymkeep`), el usuario, la clave y activa SSH.
2. Arranca la Pi y actualiza: `sudo apt update && sudo apt full-upgrade -y && sudo reboot`.
3. Comprueba que es de 64 bits: `uname -m` debe decir `aarch64`.
4. Copia el repositorio: `git clone https://github.com/Luissalamanca23/CAPSTONE_Grupo6_PM.git`
   y entra a la carpeta `CAPSTONE_Grupo6_PM/GymKeep`.

## 3. Instalar y levantar

Desde `GymKeep/`:

```bash
bash raspberry-pi/instalar-raspberry.sh --camara "rtsp://usuario:clave@192.168.1.50:554/stream"
```

El script:

1. comprueba que el equipo es `aarch64`, que es una Raspberry Pi 5 y que hay memoria suficiente;
2. instala Docker Engine y el plugin Compose desde el repositorio oficial de Docker para Debian
   (si Docker ya está instalado, lo deja como está) y exige Compose 2.24 o superior;
3. crea el archivo `.env` con claves aleatorias (PostgreSQL, MongoDB, clave del pipeline y PIN de
   edición de visión). No pisa un `.env` que ya exista. El `.env` no se sube a git;
4. levanta todo con `docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.rpi.yml up -d --build`.

Sin cámara se omite `--camara` y queda todo menos la visión; para agregarla después se edita
`VISION_FUENTE` en `.env` y se repite el comando. Para probar con un video, se copia a
`vision/datos/` y se usa `--video nombre.mp4` (más `--tiempo-real --repetir` en `VISION_OPCIONES` si
se quiere que se comporte como una cámara en vivo).

La primera vez tarda varios minutos: compila la web, instala PyTorch para CPU y exporta el modelo
NCNN, de modo que después la Pi no necesita internet para arrancar.

Luego se crea la primera cuenta (equivale a `crear-admin.bat`):

```bash
bash raspberry-pi/crear-admin.sh
```

El panel queda en `http://gymkeep.local` (o la IP de la Pi) desde cualquier equipo de la red.

## 4. Qué configura `docker-compose.rpi.yml`

| Servicio | Configuración | Motivo |
|---|---|---|
| `frontend` | nginx en el puerto 80 con el panel compilado y `/api/v1` en el mismo origen | Un solo puerto; no hay que abrir la API a la red |
| `api` | Escucha solo en `127.0.0.1:8000`; tope de 768 MB | El acceso de la red pasa por nginx |
| `db` | `shared_buffers=256MB`, `max_connections=40`; tope de 1 GB | Una sede no necesita más conexiones |
| `mongo` | `--wiredTigerCacheSizeGB 0.5`; tope de 1 GB | Sin tope, MongoDB toma la mitad de la RAM |
| `vision` | Perfil `rpi` (2,5 análisis/s, YOLO solo con movimiento, modelo NCNN), 2 CPU y 2 hilos por cámara; tope de 3 GB | Deja núcleos libres para la API y las bases |
| `respaldo-*` | Respaldo diario automático de ambas bases en `respaldos/auto/` | RNF-21; ver `respaldo/LEEME.md` |

Los topes de memoria y CPU son valores de configuración, no consumos medidos. Con más de una
cámara, bajar `VISION_HILOS` y subir `VISION_CPUS` solo si el equipo tiene margen (se comprueba
con la medición de la sección 6).

Se usa MongoDB 7 a propósito: hay un informe de que MongoDB 8.0.5 o posterior se cae al arrancar
en ARM64 con Raspberry Pi 5 (SERVER-129295), así que no se debe subir de versión sin probar.

## 5. Operación

```bash
cd GymKeep
C="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.rpi.yml"
$C ps                       # estado de los servicios
$C logs -f vision           # lo que hace el módulo de visión
$C restart vision           # reiniciar solo la visión
$C down                     # apagar (los datos quedan en los volúmenes)
git pull && $C up -d --build   # actualizar a la última versión
```

- **Arranque con la Pi:** Docker se habilita al arrancar y todos los contenedores tienen
  `restart: unless-stopped`, así que el sistema vuelve solo después de un corte de luz.
- **Respaldo y restauración:** respaldo diario a las 06:00 UTC (03:00 en Chile en verano), con
  retención de 7 días en `respaldos/auto/`. Procedimiento de restauración en `respaldo/LEEME.md`.
  Copia esa carpeta fuera de la Pi de vez en cuando: si falla el disco se pierde también el respaldo.
- **Acceso desde fuera de la sede:** no se abre ningún puerto del router. Si hace falta, usar una
  red privada (en las pruebas del proyecto se usó Tailscale).

## 6. Qué medir (cifras para el informe)

Con la visión procesando, en la Pi:

```bash
python3 raspberry-pi/medir_raspberry.py --duracion 600 --camara CAM-01
```

Deja en `raspberry-pi/mediciones/` un CSV con las muestras y un resumen con: modelo de la Pi y
memoria, opciones de visión usadas, análisis por segundo, ms por análisis, CPU total y de la
visión, temperatura, frecuencia y si hubo limitación por calor o voltaje. Lo que no se puede leer
queda como «no disponible»; el script no inventa datos.

- **Análisis por segundo:** con una cámara en vivo es el ritmo real. Con un video en
  `--tiempo-real` el pipeline lo frena a su ritmo configurado, así que no mide la capacidad máxima;
  para eso está la latencia.
- **ms por análisis:** lo que tarda el cómputo de un análisis. De ahí sale la capacidad estimada
  por cámara (1000 / latencia media) y cuántas cámaras caben: se confirma poniendo más cámaras y
  repitiendo la medición, no solo por cálculo.
- **Exactitud frente al perfil normal:** procesar el mismo video dos veces, sin `--perfil` y con
  `--perfil rpi`, y comparar los resúmenes:

  ```bash
  python -m gymkeep_vision procesar video.mp4 -c vision/config/video2.yaml --sin-video -o salida_normal
  python -m gymkeep_vision procesar video.mp4 -c vision/config/video2.yaml --sin-video --perfil rpi -o salida_rpi
  python3 raspberry-pi/comparar_perfiles.py salida_normal/resumen.json salida_rpi/resumen.json
  ```

  Para una medición limpia, correr cada una sin otra cámara en paralelo y con la Pi ya a
  temperatura estable. Ambas corridas deben usar el mismo modelo e `imgsz`.

Referencia externa (no es una medición de GymKeep): la guía de Ultralytics informa unos 67 ms por
imagen para YOLO26n en NCNN a 640 px en una Raspberry Pi 5 y recomienda medir en cada equipo,
porque el enfriamiento, el sistema y la fuente cambian el resultado.

## 7. Seguridad al instalar en una sede

- Cambiar la clave de fábrica de la cámara, actualizar su firmware, no exponerla a internet y, si
  se puede, ponerla en una red o VLAN propia.
- Las claves del `.env` son únicas por instalación: no reutilizar las de otra sede ni compartirlas.
- Servir el panel por HTTPS si se accede por fuera de la red local (la cookie de sesión se marca
  `Secure` solo con HTTPS).
- Avisar con señalética que hay cámaras. El análisis ocurre en la Pi y los rostros se difuminan.

## 8. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `gymkeep_mongo` se reinicia con *Illegal instruction* | Equipo anterior a la Pi 5 | MongoDB 7 no corre en una Pi 4; usar una Pi 5 |
| La web carga pero el inicio de sesión falla | El `Origin` del navegador no coincide con el host | Entrar por el nombre o la IP de la Pi; si es otro nombre, agregarlo a `CORS_ORIGINS` en `.env` |
| `vision` queda en bucle con «No existe el video» | `VISION_FUENTE` apunta a un archivo que no está en `vision/datos/` | Copiar el video o usar una URL `rtsp://` |
| `vision` se reinicia sin mensaje | Falta de memoria | `docker stats`; bajar a una cámara o subir `mem_limit` |
| El análisis por segundo cae con el tiempo | Limitación por calor (`vcgencmd get_throttled`) | Revisar el enfriador y la ventilación |
| El script de instalación pide cerrar sesión | El usuario recién se agregó al grupo `docker` | Cerrar sesión, volver a entrar y repetir el comando |
