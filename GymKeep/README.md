# GymKeep — Backend + Panel Web

Sistema de gestion inteligente del mantenimiento de equipamiento en gimnasios.

## Esquema de base de datos (ampliado)

Este proyecto usa el esquema completo definido en `GymKeep_BDD_Completa/` (PostgreSQL +
MongoDB + MinIO/S3), ya integrado al backend y al panel web:

```text
EMPRESA
  └── SUCURSAL
       ├── ZONA
       │    ├── CAMARA
       │    └── EQUIPO
       │         ├── QR (historico, revocable)
       │         ├── INCIDENCIA ── TIPO_FALLA (catalogo)
       │         │     └── MANTENIMIENTO
       │         └── SESION_USO
       └── MongoDB: eventos_ia / detecciones_raw / telemetria_camaras
```

Cambios clave respecto a la version anterior (ver `GymKeep_BDD_Completa/INTEGRACION_REPO_ACTUAL.md`):

- El equipo ya no tiene un `codigo_qr` fijo: el QR es una entidad propia (`qr_equipos`),
  con token UUID, que puede **revocarse y reemitirse** sin perder el historial.
- El tipo de falla ya no es un enum fijo: es un **catalogo administrable**
  (`tipos_falla`), con su propia `prioridad_base` y flags `permite_reporte_qr` /
  `permite_deteccion_ia`.
- El equipamiento se registra dentro de una jerarquia `empresa → sucursal → zona`.
- Se agrega el modelo de camaras/IA (`camaras`, `modelos_ia`, `eventos_ia_resumen`,
  `sesiones_uso`) y auditoria (`registros_auditoria`). El modulo de vision por computadora
  (`vision/`) ya alimenta `sesiones_uso` a traves de `POST /eventos-ia/`.

## Que incluye

1. **Backend (API)**:
   - **Empresas / sucursales / zonas**: jerarquia base donde se registra todo lo demas.
   - **Gestion de equipamiento**: alta, consulta, actualizacion y baja de maquinas. Al
     crear un equipo se le emite automaticamente un **QR activo** (token UUID); puede
     regenerarse (revoca el anterior y emite uno nuevo) con
     `POST /equipamiento/{id}/regenerar-qr`.
   - **Reporte de incidencias**: registro de fallas de un equipo. Cada incidencia guarda
     automaticamente **fecha y hora** (`fecha_reporte`), un **origen** (`qr`, `ia`,
     `tecnico`, `sistema`), un **tipo de falla** (del catalogo `tipos_falla`), un
     **estado** (`pendiente`, `en_proceso`, `resuelta`, `descartada`) y una **prioridad**
     (`baja`, `media`, `alta`, `urgente`) que se **clasifica sola** segun la
     `prioridad_base` del tipo de falla elegido:

     | Tipo de falla (codigo)   | Prioridad base | ¿Disponible en el QR publico? |
     |--------------------------|-----------------|--------------------------------|
     | ROTA                     | Urgente         | Si                             |
     | NO_ENCIENDE              | Urgente         | Si                             |
     | MOVIMIENTO_ANOMALO       | Alta            | No (solo lo detecta la IA)     |
     | SONIDO_EXTRANO           | Media           | Si                             |
     | OTRO                     | Media           | Si                             |
     | DESGASTE                 | Baja            | Si                             |

     Un tecnico puede reclasificar el estado/prioridad manualmente desde el panel, o
     crear una incidencia manual desde `POST /incidencias/`.
   - **Codigo QR por equipo**: `GET /equipamiento/{id}/codigo-qr` genera una imagen PNG
     que, al escanearse, abre el formulario publico de reporte para ese equipo. Pensado
     para imprimir y pegar en la maquina.
   - **Camaras / modelos de IA / eventos de IA**: inventario de camaras y sus modelos,
     con `POST /eventos-ia/` para recibir los eventos del modulo de vision (documento
     completo a MongoDB, resumen consultable en `eventos_ia_resumen`). Los eventos de uso
     (`inicio_uso` / `uso_en_curso` / `fin_uso`) se consolidan en `sesiones_uso`, y el
     endpoint es idempotente por `event_uuid` (reenviar un evento no lo duplica).
   - **Sesiones de uso / horometro**: `GET /sesiones-uso/` lista las sesiones de uso de
     cada equipo y `GET /sesiones-uso/horometro` entrega las horas de uso acumuladas por
     equipo (union de intervalos: dos sesiones solapadas no suman doble).
2. **Panel Web de gestion** (frontend), con menu lateral:
   - **Panel**: resumen y cola de incidencias ordenada por prioridad.
   - **Equipamiento**: alta de equipos (elige sucursal/zona), miniatura del QR, cambio
     de estado.
   - **Equipo → Ver detalle**: imagen QR descargable para imprimir, boton para
     **regenerar el QR**, y el historial de incidencias de esa maquina (fecha/hora, tipo
     de falla, origen, quien reporto, prioridad, estado).
   - **Incidencias**: listado filtrable por estado, ordenado por prioridad.
   - **Sucursales**: alta de empresa (si no existe ninguna), sucursales y zonas — base
     necesaria para poder registrar equipamiento.
3. **Formulario publico de reporte** (`/reportar/:token`, token del QR): a esta pagina
   llega quien escanea el QR pegado en la maquina. Es una encuesta, no un formulario de
   texto: se elige el tipo de falla tocando una opcion (solo se muestran los tipos con
   `permite_reporte_qr = true`), y el **unico campo de texto libre es el nombre** de
   quien reporta.
4. **Modulo de vision por computadora** (`vision/`, entorno propio): mide el uso y el
   tiempo de uso de cada maquina desde el video de una camara fija (YOLO26 + ByteTrack +
   una ROI por maquina + reglas T_on / T_off) y envia los eventos a la API. Ver
   `vision/README.md`.

## Stack

- Backend: Python 3.11 + FastAPI + SQLAlchemy 2.0 + PostgreSQL + MongoDB + MinIO/S3 + `qrcode`
- Frontend: React + Vite + Tailwind CSS + React Router
- Tests backend: pytest + SQLite en memoria (no requieren Docker corriendo)

## Estructura

```text
GymKeep/
├── app/
│   ├── main.py                     # Punto de entrada (incluye CORS para el frontend)
│   ├── init_db.py                  # Respaldo de desarrollo (SQLite/sin Docker); ver nota abajo
│   ├── core/                       # config (incluye Mongo/S3), database, mongo, storage
│   ├── models/gymkeep.py           # Todos los modelos del esquema ampliado (ver arriba)
│   ├── schemas/, crud/             # empresa, sucursal, zona, equipamiento, incidencia,
│   │                                 camara, modelo_ia, ai_event
│   ├── services/ai_event_service.py  # Puente Postgres <-> MongoDB para eventos de IA
│   └── api/v1/                     # empresas, sucursales, zonas, equipamiento,
│                                      incidencias, camaras, modelos_ia, eventos_ia,
│                                      sesiones_uso
├── tests/
├── vision/                         # Modulo de vision por computadora (ver vision/README.md)
├── frontend/
│   └── src/
│       ├── layouts/AdminLayout.jsx        # Menu lateral del panel
│       ├── pages/Reportar.jsx             # Formulario publico (encuesta) del QR
│       ├── pages/EquipoDetalle.jsx        # QR descargable/regenerable + historial
│       ├── pages/Sucursales.jsx           # Alta de empresa/sucursal/zona
│       ├── pages/Dashboard.jsx, Equipos.jsx, Incidencias.jsx
│       └── api/client.js
├── postgres/schema.sql, postgres/seed.sql   # Esquema completo + datos de ejemplo
├── mongo/init-mongo.js                      # Colecciones de IA (con TTL)
├── docker-compose.yml                       # Postgres + Mongo + MinIO + API
├── Dockerfile
├── requirements.txt
├── .env.example
└── GymKeep_BDD_Completa/                    # Paquete original de diseño de la BDD (referencia)
```

## IMPORTANTE: hay que reiniciar la base de datos antes de probar esta version

El esquema cambio de forma importante (empresa/sucursal/zona, QR como tabla propia,
catalogo de tipos de falla, camaras/IA). Como el proyecto todavia esta en desarrollo (solo
había datos de prueba), la estrategia adoptada es la que recomienda
`GymKeep_BDD_Completa/INTEGRACION_REPO_ACTUAL.md`: reiniciar el volumen de Postgres y
partir del esquema nuevo.

```bash
cd GymKeep
docker compose down -v   # -v borra los volumenes (datos de prueba de Postgres/Mongo/MinIO)
docker compose up --build
```

## Como correrlo

### 1) Backend

```bash
cd GymKeep
cp .env.example .env
docker compose up --build
```

Esto levanta **cuatro servicios**: PostgreSQL (`5432`), MongoDB (`27017`), MinIO
(API `9000`, consola `9001`) y la API (`8000`). Postgres carga automaticamente
`postgres/schema.sql` y `postgres/seed.sql` la primera vez (incluye una empresa,
sucursal y zona de ejemplo). API en `http://localhost:8000` (docs en
`http://localhost:8000/docs`).

### 2) Frontend

```bash
cd GymKeep/frontend
npm install
cp .env.example .env
npm run dev
```

Panel en `http://localhost:5173`.

### 3) Probar el flujo del QR

1. Si es la primera vez, revisa **Sucursales** en el panel: deberia existir ya la
   sucursal de ejemplo (`PM-01`) con la zona `Cardio` (cargadas por `postgres/seed.sql`).
   Si no existe, créala ahí mismo.
2. Crea un equipo desde **Equipamiento** (elige sucursal/zona).
3. Haz clic en **Ver detalle** → aparece la imagen del QR.
4. Escanea el QR con el celular (debe estar en la misma red que tu compu, o simplemente
   copia el enlace que aparece bajo el QR y ábrelo en otra pestaña).
5. Se abre el formulario publico: elige un tipo de falla, escribe un nombre y envía. La
   incidencia queda registrada con fecha/hora, origen `qr` y prioridad automática,
   visible en **Incidencias** y en el historial del equipo.

## Tests

```bash
cd GymKeep
pip install -r requirements.txt   # importante: agrega pymongo y boto3
pytest
```

Los tests usan SQLite en memoria (no necesitan Docker/Postgres/Mongo corriendo), pero
**si** necesitan que `pymongo` y `boto3` esten instalados (son import de `app.core.mongo`
/ `app.core.storage`, aunque no se conecten de verdad durante los tests).

`pytest.ini` limita esta corrida a `tests/`. El modulo de vision tiene sus propios tests y
su propio entorno: `cd vision && .venv/bin/python -m pytest` (ver `vision/README.md`).

## Proximos pasos

- Mostrar en el panel las horas de uso y las sesiones de cada equipo (ya expuestas en
  `GET /sesiones-uso/`), distinguiendo uso medido de estimado.
- Conectar de verdad MinIO al pipeline de IA (`app/core/storage.py::subir_evidencia`) para
  guardar snapshots/clips de evidencia.
- Modulo de costos/repuestos y dashboard financiero (Costo Total de Propiedad).
- Autenticacion para el panel (por ahora de acceso libre, para desarrollo).
- Migrar a Alembic para versionar cambios de esquema sin tener que resetear la base de
  datos cada vez (el paquete `GymKeep_BDD_Completa/alembic/` trae un punto de partida).
- Frontend movil/PWA dedicado para el escaneo de QR.
