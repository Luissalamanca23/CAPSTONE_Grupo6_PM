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
| `resumen.json` | Por máquina: sesiones, uso total, % de ocupación; parámetros y rendimiento |
| `linea_de_tiempo.png` | Detecciones crudas vs. sesiones por máquina |
| `video_anotado.mp4` | Video con ROI, personas, estado de cada máquina y cabezas difuminadas |
| `eventos.jsonl` | Los eventos exactamente como se envían a `POST /eventos-ia/` |
| `presencia.csv` | La señal cruda por máquina y por instante (sirve para `recalibrar`) |
| `evidencias/` | Un cuadro anotado por cada `inicio_uso` |

Opciones útiles: `--inicio 2026-09-26T18:00:00` (hora real del primer cuadro), `--max-segundos 120`
(prueba corta), `--desde 300`, `--sin-video` (más rápido), `--mostrar` (ventana en vivo),
`--t-on / --t-off / --confianza / --escala-tiempo` (sobrescriben el YAML).
La fuente también puede ser una cámara: `rtsp://usuario:clave@ip/stream` o `0` (webcam).

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
Reenviar es seguro: la API es idempotente por `event_uuid`. Resultado en `GET /api/v1/sesiones-uso/`
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
| `parametros.intervalo_analisis_s` | Cada cuánto se analiza un cuadro | 0,2 s |
| `parametros.criterio_zona` | `pie` (centro inferior de la persona), `centro` o `solape` | `pie` |
| `escala_tiempo` | Segundos reales por segundo de video (videos de grabador acelerados) | 1,0 |
| `modelo.pesos`, `modelo.imgsz` | Modelo YOLO y resolución de inferencia | `yolo26n.pt`, 640 |
| `privacidad.difuminar_personas` | Difumina cabezas en video y evidencias | `true` |

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
│   ├── reporte.py      # sesiones.csv, resumen.json, linea_de_tiempo.png
│   ├── recalibrar.py   # barrido de parámetros contra verdad de terreno
│   ├── calibrar.py     # herramientas para dibujar/revisar ROI
│   ├── config.py       # carga del YAML
│   └── __main__.py     # CLI
├── config/ejemplo_camara.yaml
└── tests/
```
