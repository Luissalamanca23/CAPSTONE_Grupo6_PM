# GymKeep Vision — medición de uso de máquinas con cámaras

Módulo de visión por computadora de GymKeep. Mira el video de una cámara fija y, por cada
máquina, entrega **sesiones de uso** (inicio, fin, duración). Esas sesiones llegan a la API
(`POST /api/v1/eventos-ia/`), se consolidan en `sesiones_uso` y dan las **horas de uso por
equipo** (`GET /api/v1/sesiones-uso/horometro`), base del mantenimiento preventivo por uso del
estudio (`../Estudio_Modelo_Preventivo_Mantenimiento.md`, §6.6).

```text
video / RTSP ──► YOLO26 (personas) ──► ByteTrack (ID entre cuadros) ──► ROI por máquina
                                                                            │
      sesiones_uso ◄── API GymKeep ◄── inicio_uso / uso_en_curso / fin_uso ◄┘
      (Postgres)       (+ Mongo)        máquina de estados T_on / T_off
```

**Cómo se interpreta el uso.** Una persona detectada sobre una máquina no es una sesión: la
presencia tiene que durar `t_on_s` (30 s) para abrirla y la ausencia `t_off_s` (90 s) para
cerrarla, así el descanso entre series no la parte en dos. El inicio es cuando llegó la persona
y el fin es la última vez que se la vio. Todo se mide con el reloj, nunca contando cuadros.

## Instalación

Tiene su propio entorno (no se mezcla con el del backend). Con [uv](https://docs.astral.sh/uv/):

```bash
cd GymKeep/vision
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt
```

o con pip: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`.
Los pesos de YOLO se descargan solos a `modelos/` la primera vez. Funciona en CPU; con GPU
NVIDIA se usa automáticamente.

Los videos van en `datos/` y los resultados quedan en `salida/`. **Ninguna de las dos carpetas se
sube al repositorio**, igual que `modelos/` y `privado/`.

## Uso

Todos los comandos se corren desde `GymKeep/vision` con `.venv/bin/python -m gymkeep_vision ...`.

### 1. Procesar un video

```bash
.venv/bin/python -m gymkeep_vision procesar datos/mi_video.mp4 -c config/mi_camara.yaml
```

Deja en `salida/<video>_<fecha>/`:

| Archivo | Qué es |
|---|---|
| `sesiones.csv` | Una fila por sesión: máquina, inicio, fin, duración, tiempo con alguien encima, pausas, confianza, motivo de cierre |
| `resumen.json` | Por máquina: sesiones, uso total, % de ocupación; parámetros, rendimiento y de dónde salió la hora de inicio |
| `linea_de_tiempo.png` | Detecciones crudas vs. sesiones por máquina, con la hora real en el eje |
| `video_anotado.mp4` | Video con ROI, personas, cabezas y rostros difuminados. Muestra la hora real, la posición en el video y el cronómetro de cada máquina (sesión en curso, o cuánto falta para T_on / T_off). Se reproduce al ritmo del reloj real, aunque el archivo venga acelerado |
| `eventos.jsonl` | Los eventos exactamente como se envían a `POST /eventos-ia/` |
| `presencia.csv` | La señal cruda por máquina y por instante (sirve para `recalibrar`) |
| `evidencias/` | Un cuadro anotado por cada `inicio_uso` |

**Hora real.** Todo se registra con la hora real del primer cuadro más el tiempo transcurrido
(con milisegundos). Esa hora sale, en este orden, de `--inicio 2026-09-26T18:00:00`, de los
metadatos del video (`creation_time`) o de la hora en que se procesa. En un video exportado desde
un grabador, los metadatos suelen tener la hora de exportación, no la de grabación: para una
grabación, usar siempre `--inicio`. El origen queda en `resumen.json` y el pipeline avisa si no
vino de `--inicio`.

Otras opciones: `--max-segundos 120` (prueba corta), `--desde 300`, `--sin-video` (más rápido), `--mostrar` (ventana en vivo),
`--t-on / --t-off / --confianza / --escala-tiempo` (sobrescriben el YAML).
La fuente también puede ser una cámara: `rtsp://IP_DE_LA_CAMARA/RUTA` o `0` (webcam). Si se corta
la señal, el pipeline reintenta solo (1 a 30 s); pasados `t_off_s` segundos sin cuadros cierra
las sesiones con motivo `sin_senal`. Con `--api`, la clave del pipeline se pasa con
`--clave-pipeline` o la variable `VISION_PIPELINE_KEY` (también en `enviar`).

### 2. Enviar a GymKeep

Con el backend levantado (`docker compose up -d db mongo api` en `GymKeep/`):

```bash
# En vivo, mientras procesa:
.venv/bin/python -m gymkeep_vision procesar datos/mi_video.mp4 -c config/mi_camara.yaml \
    --api http://localhost:8000 --registrar

# O reenviar una corrida ya hecha (no vuelve a correr YOLO):
.venv/bin/python -m gymkeep_vision enviar salida/<corrida>/eventos.jsonl -c config/mi_camara.yaml \
    --api http://localhost:8000 --registrar
```

`--registrar` crea en GymKeep la cámara, los equipos (`codigo_activo`) y el modelo que falten.
Los eventos que la API no alcanzó a recibir quedan en `<salida>/eventos_pendientes.jsonl` y se
reintentan solos al volver a procesar con la misma carpeta. Reenviar es seguro: la API es idempotente por `event_uuid`. Resultado en `GET /api/v1/sesiones-uso/`
y `GET /api/v1/sesiones-uso/horometro` (`http://localhost:8000/docs`).

### 3. Calibrar parámetros sin volver a correr YOLO

Los valores del YAML son un punto de partida: **se calibran por cámara**. Una cámara de baja
resolución, por ejemplo, necesita una confianza mínima más baja y más gracia.

```bash
.venv/bin/python -m gymkeep_vision recalibrar salida/<corrida> -c config/mi_camara.yaml \
    --verdad mi_verdad.csv --confianza 0.25 0.3 0.5 --gracia 2 5 10
```

Vuelve a pasar `presencia.csv` por la máquina de estados con cada combinación. Con `--verdad`
(un CSV anotado a mano: `maquina,inicio_s,fin_s`, una fila por uso real; una fila sin tiempos
significa "sin uso") muestra el error de uso y el IoU temporal de cada combinación. `procesar`
también acepta `--verdad` y agrega la comparación al resumen y al gráfico.

### 4. Definir las ROI de una cámara nueva

```bash
# Ventana interactiva: clic = punto, ENTER = cerrar máquina, U = deshacer, S = guardar
.venv/bin/python -m gymkeep_vision calibrar datos/mi_video.mp4 -o config/mi_camara.yaml --t 60

# Revisar (o dibujar a mano) sobre un cuadro con grilla de coordenadas:
.venv/bin/python -m gymkeep_vision cuadro datos/mi_video.mp4 -c config/mi_camara.yaml --t 60 -o cuadro.png
```

La ROI de una máquina es la zona del piso o del asiento donde **apoya los pies quien la usa** (el
punto blanco bajo cada persona en el video anotado). Quien está de pie al lado no debe caer dentro.
Cada máquina debe quedar **completa dentro del cuadro**: si su ROI toca el borde, el pipeline
avisa que su uso puede quedar subestimado. Conviene una cámara elevada.

### 5. En vivo, con la plataforma

```bash
.venv/bin/python -m gymkeep_vision procesar rtsp://IP_DE_LA_CAMARA/RUTA \
    --api http://localhost:8000 --camara CAM-01 --sin-video
```

Con `--camara`, las zonas y los parámetros salen de la plataforma (se dibujan en el panel y el
pipeline los relee cada 5 s), y el estado de cada máquina y la imagen se envían en vivo a la API
(registro en MongoDB). También corre en Docker, en CPU: `docker-compose.vision.yml`. La guía de la
integración con el panel (endpoints, datos y pantallas) está en [`INTEGRACION.md`](INTEGRACION.md).

## Configuración de una cámara

Plantilla comentada: [`config/ejemplo_camara.yaml`](config/ejemplo_camara.yaml).

| Campo | Qué es | Valor inicial |
|---|---|---|
| `camara.codigo`, `sucursal_codigo`, `zona_nombre` | Cómo se encuentra la cámara en GymKeep | — |
| `maquinas[].codigo_activo` | Enlace con `equipos.codigo_activo` | — |
| `maquinas[].roi` | Polígono `[[x,y], ...]` o rectángulo `{x,y,w,h}` (formato de `camara_equipos.roi`) | — |
| `parametros.t_on_s` | Presencia continua para abrir sesión (MP-45) | 30 s |
| `parametros.t_off_s` | Ausencia continua para cerrarla (MP-46); debe superar el descanso entre series | 90 s |
| `parametros.confianza_min` | Confianza mínima de una persona para contar (MP-47) | 0,50 |
| `parametros.gracia_s` | Huecos de detección que no cuentan como ausencia | 2 s |
| `parametros.t_max_s` | Duración máxima de una sesión: al superarla se cierra (`t_max`) y, si sigue habiendo presencia, empieza otra | 10800 s |
| `actividad.habilitada` | Mide la actividad con el modelo de pose (`yolo26n-pose.pt`, o `--actividad`): quien está encima de la máquina sin entrenar no cuenta como uso | `false` |
| `actividad.umbral` | Movimiento mínimo de codos, muñecas, rodillas y tobillos (en alturas de la persona, ventana de 4 s) para contar como activa | 0.08 |
| `parametros.intervalo_analisis_s` | Cada cuánto se analiza un cuadro | 0,2 s |
| `parametros.criterio_zona` | `pie` (centro inferior de la persona), `centro` o `solape` | `pie` |
| `escala_tiempo` | Segundos reales por segundo de video (videos de grabador acelerados) | 1,0 |
| `modelo.pesos`, `modelo.imgsz` | Modelo YOLO y resolución de inferencia | `yolo26n.pt`, 640 |
| `privacidad.difuminar_personas` | Difumina cabezas y rostros (YuNet) en video, evidencias e imagen del panel | `true` |

## Uso frente a presencia (actividad)

Con `--actividad` (o `actividad.habilitada: true`), el pipeline usa la versión con pose del
modelo y mide cuánto se mueven brazos y piernas de cada persona (`gymkeep_vision/actividad.py`):

- Una persona quieta sobre la máquina (sentada mirando el celular, conversando) cuenta como
  ausencia para T_on y T_off: no abre ni sostiene una sesión. La máquina se muestra
  **"ocupada sin uso"** (`ocupada`) y no suma horas.
- El descanso entre series sigue dentro de la sesión mientras dure menos que T_off. Si alguien
  se queda quieto más que eso, la sesión se cierra con `cierre = "inactividad"`, en su último
  movimiento.
- Medido en videos de gimnasio: quieto da 0.01–0.06 y un ejercicio 0.12–0.75. En 10 minutos de una
  sala con 7 máquinas, el uso registrado bajó un 23 %: lo descartado era gente sentada o
  conversando junto a las máquinas (por ejemplo, un entrenador de pie al lado de una banca).
- La pose reemplaza al detector (también detecta personas), así que el costo por cuadro es
  similar. En cámaras de baja resolución, donde la pose no es confiable, conviene no activarla.

Con varias cámaras en el mismo equipo, `VISION_HILOS` (por ejemplo `2`) limita los hilos de cada
pipeline y hace que esperen sin consumir CPU.

## Equipos chicos (Raspberry Pi 5, notebook sin GPU)

`--perfil rpi` combina los ajustes que bajan el costo sin cambiar lo que se mide:

| Opción | Qué hace |
|---|---|
| `--intervalo 0.4` | 2,5 análisis por segundo en vez de 5: T_on es 30 s y la actividad mira 4 s, así que alcanza |
| `--movimiento` | Corre YOLO solo si algo cambió cerca de las máquinas; si no, repite las detecciones anteriores (al menos un análisis cada 3 s) |
| `--ncnn` | Modelo en formato NCNN, el más rápido en CPU ARM. Se exporta solo la primera vez (necesita internet esa vez) |

Medido en CPU con 4 núcleos, 10 minutos de video con `--actividad`:

| Configuración | CPU | Uso medido |
|---|---|---|
| 5 análisis/s (por defecto) | 283 s | referencia |
| `--intervalo 0.4` | 156 s (−45 %) | igual (±2 s por máquina) |
| `--intervalo 0.4 --movimiento`, sala llena | 152 s (−46 %) | igual; YOLO se saltó 4 % de los análisis |
| `--intervalo 0.4 --movimiento`, sala tranquila | −41 % adicional | igual; YOLO se saltó 42 % de los análisis |
| `--imgsz 480` | −16 % | **peor**: la pose de las personas lejanas sale tan chica que parecen quietas (no se usa en el perfil) |

NCNN no gana en un PC x86 (es más lento que PyTorch ahí); su ventaja es en ARM y hay que medirla
en la Raspberry. Si no conviene, `--intervalo 0.4 --movimiento` da el mismo ahorro sin NCNN.
Con varias cámaras en el mismo equipo, usar también `VISION_HILOS`.

## Tests

```bash
.venv/bin/python -m pytest        # máquina de estados, zonas, configuración, recalibración
```

No necesitan GPU, video ni backend (usan datos sintéticos). Los tests del backend
(`GymKeep/tests/`, incluye `test_eventos_ia.py`) se corren aparte desde `GymKeep/` con `pytest`.

## Estructura

```text
vision/
├── gymkeep_vision/
│   ├── sesiones.py     # máquina de estados T_on / T_off (sin video, 100 % testeable)
│   ├── zonas.py        # ROI y asignación persona -> máquina (una persona, una máquina)
│   ├── pipeline.py     # video -> YOLO + ByteTrack -> zonas -> estados -> eventos + video anotado
│   ├── eventos.py      # formato EventoIACreate, envío a la API, resolución de IDs
│   ├── vivo.py         # envío en vivo a la plataforma y relectura de zonas
│   ├── tiempo.py       # hora real de cada cuadro y formatos
│   ├── reporte.py      # sesiones.csv, resumen.json, linea_de_tiempo.png
│   ├── recalibrar.py   # barrido de parámetros contra verdad de terreno
│   ├── calibrar.py     # herramientas para dibujar/revisar ROI
│   ├── config.py       # carga del YAML
│   └── __main__.py     # CLI
├── config/ejemplo_camara.yaml
├── Dockerfile          # pipeline en CPU (ver ../docker-compose.vision.yml)
├── INTEGRACION.md      # guía de la integración con el panel
└── tests/
```
