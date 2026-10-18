# GymKeep — Backend + Panel Web

Sistema de gestión inteligente del mantenimiento de equipamiento en gimnasios: registro
de máquinas, reporte de fallas por código QR, seguimiento de incidencias y mantenimientos,
y control de gastos.

## Qué incluye

### 1. Backend (API — FastAPI)

- **Empresas / sucursales / zonas**: jerarquía base donde se registra todo lo demás. Para
  este Capstone normalmente hay una sola empresa/sucursal (la de `postgres/seed.sql`), pero
  el modelo soporta más de una.
- **Equipamiento**: alta, consulta, actualización y baja de máquinas, con **categoría**
  (cardio / fuerza / funcional / peso libre / otro) además de marca, modelo, sucursal y
  zona. Al crear un equipo se le emite automáticamente un **QR activo** (token UUID), que
  puede regenerarse (revoca el anterior y emite uno nuevo) con
  `POST /equipamiento/{id}/regenerar-qr`.
- **Incidencias**: registro de fallas de un equipo. Cada incidencia guarda automáticamente
  **fecha y hora**, un **origen** (`qr`, `ia`, `tecnico`, `sistema` — hoy en la práctica
  todo entra por `qr`), un **tipo de falla** (del catálogo `tipos_falla`, que también trae
  su propia categoría: mecánica / eléctrica / otro), un **estado**
  (`pendiente`, `en_proceso`, `resuelta`, `descartada`) y una **prioridad**
  (`baja`, `media`, `alta`, `urgente`) que se clasifica sola según la `prioridad_base` del
  tipo de falla elegido:

  | Tipo de falla (código)   | Categoría | Prioridad base | ¿Disponible en el QR público? |
  |--------------------------|-----------|-----------------|--------------------------------|
  | ROTA                     | Mecánica  | Urgente         | Sí                             |
  | NO_ENCIENDE              | Eléctrica | Urgente         | Sí                             |
  | MOVIMIENTO_ANOMALO       | Mecánica  | Alta            | No (solo lo detecta la IA)     |
  | SONIDO_EXTRANO           | Mecánica  | Media           | Sí                             |
  | OTRO                     | Otro      | Media           | Sí                             |
  | DESGASTE                 | Mecánica  | Baja            | Sí                             |

  El listado (`GET /incidencias/`) admite filtros combinables por `estado`, `equipo_id`,
  `categoria`, `prioridad`, `fecha_desde`/`fecha_hasta` y texto libre (`q`), y devuelve el
  total real que cumple los filtros en el header `X-Total-Count` (para paginar sin traer
  todos los registros de una vez). Un técnico puede reclasificar estado/prioridad desde el
  panel, o crear una incidencia manual con `POST /incidencias/`.
- **Mantenimientos**: `POST /mantenimientos/` registra un mantenimiento ya realizado
  (correctivo o preventivo), con técnico, descripción y **costo total** opcional; puede
  dejar resueltas una o varias incidencias abiertas de ese equipo de una sola vez.
  `GET /mantenimientos/?equipo_id=...` trae el historial de un equipo puntual;
  `GET /mantenimientos/` sin `equipo_id` trae el historial completo del gimnasio (con
  filtros opcionales de `tipo`, `fecha_desde`/`fecha_hasta` y `q`), usado por la vista de
  **Costos de mantención** del panel.
- **Código QR por equipo**: `GET /equipamiento/{id}/codigo-qr` genera una imagen PNG que,
  al escanearse, abre el formulario público de reporte para ese equipo. Pensado para
  imprimir y pegar en la máquina.
- **Cámaras / modelos de IA / eventos de IA**: inventario de cámaras y sus modelos, con
  `POST /eventos-ia/` para recibir los eventos del módulo de visión (`vision/`): documento
  completo a MongoDB y resumen consultable en `eventos_ia_resumen`. Los eventos de uso
  (`inicio_uso` / `uso_en_curso` / `fin_uso`) se consolidan en `sesiones_uso`, y el endpoint
  es idempotente por `event_uuid` (reenviar un evento no lo duplica).
- **Sesiones de uso / horómetro**: `GET /sesiones-uso/` lista las sesiones de uso de cada
  equipo y `GET /sesiones-uso/horometro` entrega las horas de uso acumuladas por equipo
  (unión de intervalos: dos sesiones solapadas no suman doble).

### 2. Panel web de gestión (frontend)

Diseño responsive (menú lateral en escritorio, menú hamburguesa en celular/tablet) con un
botón flotante de **Ayuda** (preguntas frecuentes) disponible en todas las pantallas.

- **Panel**: resumen (equipos registrados, incidencias pendientes/en proceso, equipos
  fuera de servicio) y, debajo, lo que interesa al dueño del gimnasio:
  - **Atención recomendada**: avisos de incidencias urgentes/altas abiertas hace más de
    48 h, máquinas con 3 o más incidencias en 30 días y máquinas con más de 200 h de uso
    desde su última mantención (este último aviso usa los datos de las cámaras). Los
    umbrales están al inicio de `frontend/src/utils/analitica.js`.
  - **Análisis** con un único filtro de periodo (8 semanas / 6 meses / 12 meses): cifras
    del periodo comparadas con el anterior (incidencias, tasa de resolución, tiempo medio
    de resolución, gasto) y gráficos de tendencia de incidencias reportadas vs. resueltas,
    gasto correctivo vs. preventivo, tipos de falla, categorías de máquina, máquinas con
    más fallas y más gasto, mapa de calor día × franja horaria, estado de la flota y uso
    de los últimos 7 días. Cada gráfico tiene un botón **Ver tabla** con los mismos datos.
  - El monitor de máquinas por zona (con el estado en vivo de las cámaras) y la cola de
    incidencias sin resolver ordenada por prioridad, ambos paginados.
- **Equipamiento**: alta de equipos (sucursal/zona/categoría), miniatura del QR, semáforo
  de **salud del equipo** (verde/naranjo/rojo/negro según incidencias abiertas y estado),
  cambio de estado, búsqueda por texto y filtro por categoría/estado. Tabla con scroll
  contenido para listas largas.
- **Equipo → Ver detalle**: imagen QR descargable e invalidable/regenerable, historial de
  incidencias de esa máquina (con sus propios filtros de categoría/estado/fecha), formulario
  para **registrar un mantenimiento** (marca incidencias como resueltas y opcionalmente
  registra su costo), e historial de mantenimientos con el total de **gastos de
  mantención** de esa máquina.
- **Incidencias**: listado completo del gimnasio con paginación, búsqueda por texto,
  filtros por categoría/prioridad/estado y por fecha (hoy/semana/mes/rango
  personalizado), y tabla con scroll contenido para manejar cientos de registros sin que
  la página crezca sin límite.
- **Costos de mantención**: vista consolidada de todos los mantenimientos del gimnasio —
  gasto total, promedio por mantenimiento, desglose correctivo vs. preventivo, ranking de
  las máquinas con más gasto, y el detalle completo (fecha, equipo, categoría, tipo,
  técnico, qué se hizo, costo) con los mismos filtros que el historial de incidencias.
- **Sucursales**: alta de empresa (si no existe ninguna), sucursales y zonas — base
  necesaria para poder registrar equipamiento.
- **Uso de máquinas** (`/uso`): tiempo de uso de cada máquina medido por las cámaras —
  horómetro, horas de los últimos 7 días, horas desde la última mantención y chip en vivo
  ("En uso 04:39", "Detectando 12/30 s", "Libre"). Con búsqueda, orden y filtro "solo
  medidas por cámara". Al abrir una máquina (`/uso/:id`): foto de referencia (subir o
  tomar de la cámara), gráfico de uso de los últimos 30 días y pestañas de sesiones,
  incidencias y mantenciones.
- **Cámaras** (`/camaras`): lista con la última imagen y si el pipeline está en línea. En
  cada cámara (`/camaras/:id`): imagen en vivo con las zonas de las máquinas y las personas
  detectadas encima, **editor de zonas** (dibujar, arrastrar vértices, quitar), parámetros
  de detección (T_on, T_off, confianza, gracia, escala de tiempo) y subida de una imagen de
  referencia para dibujar zonas sin tener el pipeline corriendo.

### 3. Formulario público de reporte (`/reportar/:token`)

A esta página llega quien escanea el QR pegado en la máquina. Es una encuesta, no un
formulario de texto: se elige el tipo de falla tocando una opción (solo se muestran los
tipos con `permite_reporte_qr = true`); si elige "Otro" se abre un cuadro de texto libre
para describir la falla. El único otro campo es el nombre de quien reporta.

## Modelo de datos

```text
EMPRESA
  └── SUCURSAL
       ├── ZONA
       │    ├── CAMARA
       │    └── EQUIPO (con categoria propia: cardio/fuerza/funcional/peso_libre/otro)
       │         ├── QR (historico, revocable)
       │         ├── INCIDENCIA ── TIPO_FALLA (catalogo, con su propia categoria)
       │         │     └── MANTENIMIENTO (con costo_total opcional)
       │         └── SESION_USO
       └── MongoDB: eventos_ia / detecciones_raw / telemetria_camaras
```

- El QR no es un campo fijo del equipo: es una entidad propia (`qr_equipos`), con token
  UUID, que puede **revocarse y reemitirse** sin perder el historial.
- El tipo de falla no es un enum fijo: es un **catálogo administrable** (`tipos_falla`),
  con su propia `categoria`, `prioridad_base` y flags `permite_reporte_qr` /
  `permite_deteccion_ia`.
- Cámaras/IA (`camaras`, `modelos_ia`, `eventos_ia_resumen`, `sesiones_uso`) y auditoría
  (`registros_auditoria`). El módulo de visión por computadora (`vision/`) alimenta
  `sesiones_uso` a través de `POST /eventos-ia/`.

Ver `GymKeep_BDD_Completa/` para el paquete original de diseño de la base de datos
(documento de referencia; no es lo que corre en producción, eso es
`postgres/schema.sql`).

## Stack

- **Backend**: Python 3.11 + FastAPI + SQLAlchemy 2.0 + PostgreSQL 16 + MongoDB 7 +
  MinIO/S3 (opcional, ver nota abajo) + `qrcode`.
- **Frontend**: React 18 + Vite + Tailwind CSS + React Router.
- **Tests backend**: pytest + SQLite en memoria (no requieren Docker corriendo).
- Todo corre en contenedores Docker (Docker Compose); el frontend corre con Node/Vite
  fuera de Docker (más rápido para desarrollar con recarga en caliente).

## Estructura

```text
GymKeep/
├── app/
│   ├── main.py                       # Punto de entrada (CORS, routers, /health)
│   ├── init_db.py                    # Respaldo de desarrollo (SQLite/sin Docker)
│   ├── core/                         # config (incluye Mongo/S3), database, mongo, storage
│   ├── models/gymkeep.py             # Todos los modelos vigentes (ver Modelo de datos)
│   ├── models/equipamiento.py, incidencia.py  # Obsoletos, solo referencia historica
│   ├── schemas/, crud/                # empresa, sucursal, zona, equipamiento, incidencia,
│   │                                    mantenimiento, camara, modelo_ia, ai_event
│   ├── services/ai_event_service.py  # Puente Postgres <-> MongoDB para eventos de IA
│   └── api/v1/                       # empresas, sucursales, zonas, equipamiento,
│                                        incidencias, mantenimientos, camaras, modelos_ia,
│                                        eventos_ia, sesiones_uso
├── tests/                            # pytest (SQLite en memoria)
├── vision/                           # Módulo de visión por computadora (ver vision/README.md)
├── frontend/
│   └── src/
│       ├── layouts/AdminLayout.jsx         # Menu lateral/responsive + boton de Ayuda
│       ├── components/                     # Badges (Estado/Prioridad/TipoFalla/
│       │                                     Categoria/CategoriaEquipo), StatCard, FaqAyuda,
│       │                                     Paginacion, EstadoVivoChip,
│       │                                     graficos.jsx (graficos SVG propios, sin librerias)
│       ├── pages/Reportar.jsx              # Formulario publico (encuesta) del QR
│       ├── pages/EquipoDetalle.jsx         # QR, historial filtrable, mantenimientos + costo
│       ├── pages/Equipos.jsx               # Listado/alta de equipos, filtros, categorias
│       ├── pages/Incidencias.jsx           # Listado con filtros, fechas y paginacion
│       ├── pages/Costos.jsx                # Vista consolidada de gastos de mantencion
│       ├── pages/UsoMaquinas.jsx, UsoMaquinaDetalle.jsx   # Uso medido por camaras
│       ├── pages/Camaras.jsx, CamaraVista.jsx             # Camaras, zonas en vivo y editor
│       ├── pages/Dashboard.jsx, Sucursales.jsx
│       ├── utils/formato.js, saludEquipo.js, vision.js, paginacion.js,
│       │         analitica.js              # Calculos del Panel (KPIs, series, alertas)
│       └── api/client.js
├── postgres/
│   ├── schema.sql, seed.sql                # Esquema completo + datos de ejemplo minimos
│   └── reset_demo_incidencias.sql,
│       agregar_mas_datos.sql,
│       datos_demo_dashboard.sql            # Scripts opcionales para poblar datos de demo
│                                             variados (ver seccion "Datos de ejemplo")
├── mongo/init-mongo.js                      # Colecciones de IA (con TTL)
├── docker-compose.yml                       # Postgres + Mongo + API (+ MinIO opcional)
├── Dockerfile
├── requirements.txt
├── .env.example
└── GymKeep_BDD_Completa/                    # Paquete original de diseño de la BDD (referencia)
```

## Cómo levantarlo

### Requisitos (una sola vez por computador)

- **Git**.
- **Docker Desktop** (docker.com/products/docker-desktop), abierto mientras trabajas.
- **Node.js 18+** (incluye `npm`) — nodejs.org, versión LTS.

No hace falta instalar Python, Postgres ni Mongo a mano: Docker se encarga de eso.

### 1) Clonar el proyecto

```bash
git clone https://github.com/Luissalamanca23/CAPSTONE_Grupo6_PM.git
cd CAPSTONE_Grupo6_PM/GymKeep
```

### 2) Backend (Postgres + Mongo + API)

```bash
cp .env.example .env
docker compose up -d --build
```

Esto levanta **tres servicios**: PostgreSQL (`5432`), MongoDB (`27017`) y la API (`8000`).
Postgres carga automáticamente `postgres/schema.sql` y `postgres/seed.sql` la primera vez
que se crea el volumen (incluye una empresa, sucursal, zona y equipo de ejemplo). La API
queda en `http://localhost:8000` (documentación interactiva en
`http://localhost:8000/docs`).

> **MinIO es opcional.** Solo guarda fotos/videos de evidencia de cámaras, una función que
> todavía no está conectada a ningún pipeline real. Por eso **no se levanta** con el
> comando de arriba. Si alguna vez necesitas probarlo:
> ```bash
> docker compose --profile storage up -d
> ```
> (A la fecha de este README, tanto Docker Hub como quay.io dejaron de servir
> `minio/minio`/`minio/mc` de forma anónima, así que ese perfil puede fallar igual — no
> afecta al resto del sistema.)

### 3) Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Panel en `http://localhost:5173`.

El frontend llama a la API en `http://localhost:8000/api/v1` por defecto. Para apuntarlo a
otra URL (por ejemplo, el servidor de producción) define `VITE_API_URL` en
`frontend/.env` **antes** de `npm run dev` o `npm run build` (Vite la incrusta al compilar):

```bash
VITE_API_URL=https://gymkeep.ejemplo.cl/api/v1
```

### Producción con Docker

`docker-compose.prod.yml` es un override de `docker-compose.yml` (no lo reemplaza):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Requiere Docker Compose 2.24 o superior. Diferencias con desarrollo: la API usa el código
de la imagen (no se monta `./app`) y arranca sin `--reload`; Postgres y Mongo solo escuchan
en `127.0.0.1`; y las claves son obligatorias (sin valores por defecto). Si falta alguna,
`docker compose` se detiene con un mensaje. Hay que definir en el `.env`:
`POSTGRES_PASSWORD`, `MONGO_ROOT_PASSWORD`, `FRONTEND_URL`, `VISION_PIN` y
`VISION_PIPELINE_KEY`. La imagen de la API corre con un usuario sin privilegios y declara un
`HEALTHCHECK` contra `/health`.

### Notas según tu terminal (Windows)

- **PowerShell** no soporta `<` para redirigir un archivo a un comando. Si necesitas pasar
  un archivo `.sql` a `psql` (ver "Datos de ejemplo" más abajo), usa:
  ```powershell
  Get-Content archivo.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
  ```
- **cmd.exe** y **Git Bash (MINGW64)** sí soportan `<` normalmente:
  ```
  docker compose exec -T db psql -U gymkeep -d gymkeep < archivo.sql
  ```
- Si `docker compose up` falla para un contenedor que no sea `db`, `mongo` o `api`, revisa
  que no estés intentando levantar el perfil `storage` (MinIO) sin quererlo.

## Módulo de visión en el panel

El backend de visión (`/api/v1/vision/...`) viene incluido en la API. El pipeline que mira
el video (YOLO) corre aparte, en su propio contenedor, y **no** se levanta con el
`docker compose up` normal. Sin pipeline las pantallas **Uso de máquinas** y **Cámaras**
funcionan igual (se puede subir una imagen de referencia y dibujar zonas), pero sin datos
en vivo. Para verlo andando con el video de prueba:

```bash
# 1) Copia el video a GymKeep/vision/datos/cctv_cintas.mp4 (esa carpeta no se sube a git)
# 2) Desde GymKeep: UN comando levanta todo (db, mongo, api y visión):
docker compose -f docker-compose.vision.yml up -d --build
docker compose -f docker-compose.vision.yml logs -f vision     # seguir lo que hace
```

Listo: el contenedor espera a la API, deja las zonas de las 3 cintas en la cámara `CAM-01` y analiza
el video en bucle como si fuera una cámara en vivo. Se ve en el panel, **Cámaras → CAM-01**
(`http://localhost:5173/camaras`); el video en vivo también se abre directo en
`http://localhost:8000/api/v1/vision/camaras/1/stream` (cambia el `1` por el id de la cámara) y
todos los endpoints están en `http://localhost:8000/docs`, sección *vision*. La primera
construcción es lenta (descarga PyTorch y los pesos de YOLO). Las zonas iniciales son aproximadas:
se ajustan arrastrando los vértices en el panel. Para otro video o una cámara RTSP, ver las
variables `VISION_*` en `vision/INTEGRACION.md` (§6). Detalles del pipeline: `vision/README.md`.

## Ver las bases de datos

Dos visores web, solo para desarrollo (no arrancan con el `up` normal):

```bash
docker compose up -d adminer mongo-express
```

- **PostgreSQL** (Adminer): <http://localhost:8080>. Sistema `PostgreSQL`, servidor `db`, usuario
  `gymkeep`, contraseña `gymkeep_password`, base `gymkeep`. Atajo con el servidor ya elegido:
  <http://localhost:8080/?pgsql=db&username=gymkeep&db=gymkeep>.
- **MongoDB** (mongo-express): <http://localhost:8081>, sin login. Base `gymkeep_ai`
  (colecciones `camaras_vivo`, `detecciones_raw`, `telemetria_camaras`, `eventos_ia`...).

En Adminer, además de las tablas hay **vistas legibles** (las que empiezan con `v_`): equipos,
incidencias, mantenciones, sesiones de uso, cámaras y costos por mes, ya con nombres en vez de ids,
fechas en hora de Chile y montos en pesos. Son solo para mirar. Se crean solas al crear la base por
primera vez; si ya la tenías, cárgalas una vez (se pueden repetir sin problema):

```powershell
Get-Content postgres\vistas_legibles.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
```

Los puertos se cambian con `ADMINER_PORT` y `MONGO_EXPRESS_PORT` en `.env`. Si prefieres un
cliente de escritorio (DBeaver, pgAdmin, Compass), las bases también están en
`localhost:5432` (Postgres) y `localhost:27017` (Mongo) con las mismas credenciales.

## Datos de ejemplo

`postgres/seed.sql` carga solo lo mínimo (una sucursal, una zona, un equipo). Para tener
datos variados con los que probar filtros, paginación y la vista de Costos, hay dos
scripts opcionales en `postgres/` que se ejecutan contra el contenedor ya levantado:

```bash
# Windows PowerShell:
Get-Content postgres/reset_demo_incidencias.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
Get-Content postgres/agregar_mas_datos.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep

# cmd / bash / Git Bash:
docker compose exec -T db psql -U gymkeep -d gymkeep < postgres/reset_demo_incidencias.sql
docker compose exec -T db psql -U gymkeep -d gymkeep < postgres/agregar_mas_datos.sql
```

- `reset_demo_incidencias.sql`: borra las incidencias existentes y crea ~14 equipos y ~30
  incidencias variadas (todas en el mismo gimnasio/sucursal).
- `agregar_mas_datos.sql`: agrega otros ~10 equipos y ~30 incidencias más (no borra nada),
  y normaliza el origen de todas las incidencias a `qr`.

Ambos son seguros de correr más de una vez (usan `ON CONFLICT DO NOTHING` para los
equipos/zonas; las incidencias simplemente se suman).

### Historial de costos y mantenciones (para el Panel)

Para que los gráficos del Panel (tendencias, gasto, rankings, mapa de calor) tengan
sentido hace falta historia. Ejecútalo **al final**, después de los dos scripts anteriores:

```bash
# Windows PowerShell:
Get-Content postgres/datos_demo_dashboard.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep

# cmd / bash / Git Bash:
docker compose exec -T db psql -U gymkeep -d gymkeep < postgres/datos_demo_dashboard.sql
```

`datos_demo_dashboard.sql` genera ~2 años de datos relacionados entre sí: unas 5 incidencias
nuevas por semana (con más fallas lunes y martes y en horario punta), cada incidencia
resuelta con su **mantención correctiva** y un costo según el tipo de falla (una pieza rota o
un equipo que no enciende cuesta mucho más que un desgaste), **mantenciones preventivas**
periódicas por máquina, inspecciones, y algunas máquinas "problemáticas" con muchas fallas y
poca prevención. También deja incidencias urgentes sin atender y mantenciones abiertas para
que aparezcan los avisos de "Atención recomendada", y le agrega su mantención con costo a las
incidencias que ya estaban resueltas. Las fechas son relativas a hoy.

Es seguro correrlo varias veces: al empezar borra solo lo que creó una corrida anterior
(filas marcadas como demo) y lo vuelve a generar; no toca lo que hayas creado a mano. Si
después vuelves a ejecutar `reset_demo_incidencias.sql` (que borra todas las incidencias),
corre este script de nuevo.

## Probar el flujo del QR

1. Revisa **Sucursales** en el panel: debería existir la sucursal de ejemplo (`PM-01`) con
   la zona `Cardio` (cargadas por `postgres/seed.sql`). Si no existe, créala ahí mismo.
2. Crea un equipo desde **Equipamiento** (elige sucursal/zona/categoría).
3. Haz clic en **Ver detalle** → aparece la imagen del QR.
4. Escanea el QR con el celular (debe estar en la misma red que tu computador), o copia el
   enlace que aparece bajo el QR y ábrelo en otra pestaña.
5. Se abre el formulario público: elige un tipo de falla (o "Otro" + descripción libre),
   escribe un nombre y envía. La incidencia queda registrada con fecha/hora, origen `qr` y
   prioridad automática, visible en **Incidencias** y en el historial del equipo.

## Tests

```bash
cd GymKeep
pip install -r requirements-dev.txt   # requirements.txt + pytest y httpx
pytest
```

`requirements.txt` trae solo lo necesario para ejecutar la API (es lo que instala el
Dockerfile); las herramientas de prueba están en `requirements-dev.txt`. El workflow
`.github/workflows/ci.yml` corre los tests del backend, los del módulo de visión y el build
del frontend en cada push a `main` y en cada pull request.

Los tests usan SQLite en memoria (no necesitan Docker/Postgres/Mongo corriendo).
`pytest.ini` limita esta corrida a `tests/`: el módulo de visión tiene sus propios tests y
su propio entorno (`cd vision && .venv/bin/python -m pytest`, ver `vision/README.md`).

## Política de esquema de base de datos

La fuente de verdad del esquema es `postgres/schema.sql` (se carga al crear el volumen de
Postgres). Los modelos de `app/models/gymkeep.py` deben mantenerse alineados con ese
archivo. **Alembic no está configurado** en este proyecto: un cambio de esquema se hace
editando `schema.sql` y, en una base ya creada, aplicando el cambio a mano con SQL (o
recreando el volumen en desarrollo). Los tests no usan `schema.sql`: crean las tablas desde
los modelos sobre SQLite.

## Notas / problemas conocidos

- **Un solo gimnasio por ahora**: el modelo soporta varias empresas/sucursales, pero tanto
  los datos de ejemplo como los scripts de `postgres/` asumen una sola sucursal activa
  (la del seed). Si se necesita multi-sucursal real, hay que revisar esa suposición en el
  frontend (selectores, filtros) y en los scripts de demo.
- **MinIO**: quedó detrás de un profile opcional (ver arriba) porque sus imágenes Docker
  dejaron de poder descargarse de forma anónima. El módulo de visión no lo necesita.
- **Sin autenticación**: el panel es de acceso libre por ahora (pensado para desarrollo).

## Próximos pasos

- Conectar de verdad un almacenamiento de objetos al pipeline de IA
  (`app/core/storage.py::subir_evidencia`) para guardar snapshots/clips de evidencia —
  evaluar alternativas a MinIO dado el problema de distribución mencionado arriba.
- Autenticación para el panel.
- Configurar Alembic (hoy el esquema se gestiona solo con `postgres/schema.sql`) para versionar cambios de esquema sin tener que resetear la base de
  datos cada vez (el paquete `GymKeep_BDD_Completa/alembic/` trae un punto de partida).
- Soporte real para múltiples sucursales en el frontend, si el proyecto lo llega a
  necesitar.
- Frontend móvil/PWA dedicado para el escaneo de QR.


## Eliminar datos desde el panel

Cada pantalla tiene un botón **Eliminar** que abre un diálogo con lo que se llevaría el borrado (reportes,
mantenimientos, sesiones de uso, eventos de IA, QR…) y pide escribir `ELIMINAR` antes de borrar. Es
irreversible y funciona en cascada:

| Dónde | Qué borra |
|---|---|
| Equipos / detalle de máquina | La máquina con sus reportes, mantenimientos, sesiones, QR, eventos y foto. |
| Sucursales y zonas | La sucursal con zonas, máquinas, cámaras y todo lo anterior. La zona (×) solo se quita: sus máquinas y cámaras quedan sin zona. |
| Cámaras | La cámara con sus eventos de IA y estado en vivo; sus sesiones de uso y reportes se conservan sin cámara. |
| Incidencias | El reporte (los mantenimientos que lo mencionaban se conservan). |
| Detalle de máquina y Costos | El registro de mantenimiento. |

API: `GET /{recurso}/{id}/resumen-eliminacion` devuelve los conteos y `DELETE /{recurso}/{id}?forzar=true`
borra; sin `forzar`, la API se niega si hay datos asociados. Para vaciar todo de una vez (datos de prueba)
quedan `postgres/limpiar_datos_pruebas.sql` y `mongo/limpiar_datos_pruebas.js`.


## Foto de referencia de cada máquina

Al crear una máquina (Equipos → Nueva máquina) se puede elegir o tomar una foto; también se puede subir o
cambiar desde el detalle de la máquina. La foto se achica en el navegador y se guarda en MongoDB
(`fotos_equipos`) vía `PUT /api/v1/vision/maquinas/{id}/foto`, así que si `VISION_PIN` está configurado el
panel pide el PIN al subirla. Se muestra en la lista de Equipos y en el panel de uso por máquina.


## Categorías de máquinas y edición

Las máquinas se clasifican en 6 categorías: `cardio`, `placas` (placas/guiadas), `discos` (carga de discos),
`peso_libre`, `bancos_racks` y `funcional`. La API solo acepta esas al crear o editar. Para pasar las máquinas
ya ingresadas al esquema nuevo (clasifica por el nombre, guarda un respaldo y lista lo que no reconoce):

```powershell
Get-Content postgres\reclasificar_categorias.sql -Raw | docker compose exec -T db psql -U gymkeep -d gymkeep
```

Lo que quede "sin clasificar" se corrige con **Editar** (lista de Equipos o detalle de la máquina), que permite
cambiar nombre, código, categoría, zona, marca, modelo, serie, fechas, vida útil y observaciones. El filtro
"Por reclasificar / sin categoría" de la lista muestra las pendientes.


## Historial del gimnasio (datos de demostración)

Para que el Panel tenga con qué inferir, el script `postgres/historial_demo.sql` hace que el gimnasio lleve 2 años
y 8 meses abierto: fechas de instalación, vida útil por tipo de máquina, ~140.000 franjas de uso (las máquinas
más pedidas acumulan miles de horas), ~70 incidencias (concentradas en caminadoras, bicicletas y máquinas con
polea) y mantenciones con costo: una visita preventiva cada 60 días con cuota fija de $50.000 que revisa todas
las máquinas, y reparaciones con repuesto solo cuando corresponde. El gasto total no pasa de $3 millones. Todo
queda marcado como demo (`"demo": "historial3"`) y es repetible; los ajustes están al inicio del archivo.
Cómo se calibró, con fuentes: `Analisis_Vida_Util_Equipos.md`.

```powershell
docker compose cp postgres\historial_demo.sql db:/tmp/historial_demo.sql
docker compose exec db psql -U gymkeep -d gymkeep -f /tmp/historial_demo.sql
```

Reemplaza a `datos_demo_dashboard.sql` (borra lo que ese script creó). Guarda las fechas originales en
`respaldo_fechas_equipos`; al final del archivo hay un bloque DESHACER. El Panel tiene una sección
**Demanda de máquinas** que usa esas horas de uso para decidir qué máquinas sumar al ampliar o abrir otro local.
