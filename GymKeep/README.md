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
  fuera de servicio) y la cola de incidencias sin resolver, ordenada por prioridad.
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
│       │                                     Categoria/CategoriaEquipo), StatCard, FaqAyuda
│       ├── pages/Reportar.jsx              # Formulario publico (encuesta) del QR
│       ├── pages/EquipoDetalle.jsx         # QR, historial filtrable, mantenimientos + costo
│       ├── pages/Equipos.jsx               # Listado/alta de equipos, filtros, categorias
│       ├── pages/Incidencias.jsx           # Listado con filtros, fechas y paginacion
│       ├── pages/Costos.jsx                # Vista consolidada de gastos de mantencion
│       ├── pages/Dashboard.jsx, Sucursales.jsx
│       ├── utils/formato.js, saludEquipo.js
│       └── api/client.js
├── postgres/
│   ├── schema.sql, seed.sql                # Esquema completo + datos de ejemplo minimos
│   └── reset_demo_incidencias.sql,
│       agregar_mas_datos.sql               # Scripts opcionales para poblar datos de demo
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
pip install -r requirements.txt   # incluye pymongo y boto3, usados por app.core.mongo/storage
pytest
```

Los tests usan SQLite en memoria (no necesitan Docker/Postgres/Mongo corriendo).
`pytest.ini` limita esta corrida a `tests/`: el módulo de visión tiene sus propios tests y
su propio entorno (`cd vision && .venv/bin/python -m pytest`, ver `vision/README.md`).

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
- Migrar a Alembic para versionar cambios de esquema sin tener que resetear la base de
  datos cada vez (el paquete `GymKeep_BDD_Completa/alembic/` trae un punto de partida).
- Soporte real para múltiples sucursales en el frontend, si el proyecto lo llega a
  necesitar.
- Frontend móvil/PWA dedicado para el escaneo de QR.
