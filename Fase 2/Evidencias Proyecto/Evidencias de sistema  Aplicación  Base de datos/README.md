# GymKeep — Backend + Panel Web

Sistema de gestion inteligente del mantenimiento de equipamiento en gimnasios.

## Que incluye

1. **Backend (API)**:
   - **Gestion de equipamiento**: alta, consulta, actualizacion y baja de maquinas,
     cada una con un codigo QR unico.
   - **Reporte de incidencias**: registro de fallas de un equipo. Cada incidencia
     guarda automaticamente **fecha y hora** (`fecha_reporte`), tiene un
     **tipo de falla** fijo (`desgaste`, `sonido_extrano`, `rota`, `no_enciende`,
     `otro`), un **estado** (`pendiente`, `en_proceso`, `resuelta`, `descartada`)
     y una **prioridad** (`baja`, `media`, `alta`, `urgente`) que se **clasifica
     sola** segun el tipo de falla:

     | Tipo de falla     | Prioridad asignada |
     |-------------------|---------------------|
     | Rota / no funciona| Urgente             |
     | No enciende       | Urgente             |
     | Sonido extraño    | Media               |
     | Desgaste          | Baja                |
     | Otro              | Media               |

     Un tecnico puede reclasificar el estado/prioridad manualmente desde el panel.
   - **Codigo QR por equipo**: `GET /equipamiento/{id}/codigo-qr` genera una imagen
     PNG que, al escanearse, abre el formulario publico de reporte para ese equipo.
     Pensado para imprimir y pegar en la maquina.
2. **Panel Web de gestion** (frontend), con menu lateral:
   - **Panel**: resumen y cola de incidencias ordenada por prioridad.
   - **Equipamiento**: alta de equipos, miniatura del QR, cambio de estado.
   - **Equipo → Ver detalle**: imagen QR descargable para imprimir, y el
     **historial de incidencias de esa maquina** (fecha/hora, tipo de falla,
     quien reporto, prioridad, estado).
   - **Incidencias**: listado filtrable por estado, ordenado por prioridad.
3. **Formulario publico de reporte** (`/reportar/:codigoQr`): a esta pagina
   llega quien escanea el QR pegado en la maquina. Es una encuesta, no un
   formulario de texto: se elige el tipo de falla tocando una opcion, y el
   **unico campo de texto libre es el nombre** de quien reporta.

## Stack

- Backend: Python 3.11 + FastAPI + SQLAlchemy 2.0 + PostgreSQL + `qrcode`
- Frontend: React + Vite + Tailwind CSS + React Router
- Tests backend: pytest + SQLite en memoria

## Estructura

```
GymKeep/
├── app/
│   ├── main.py                 # Punto de entrada (incluye CORS para el frontend)
│   ├── init_db.py              # Script de desarrollo para crear las tablas
│   ├── core/                   # Configuracion (incluye FRONTEND_URL) y base de datos
│   ├── models/incidencia.py    # TipoFalla + clasificacion automatica de prioridad
│   ├── schemas/, crud/, api/v1/
├── tests/
├── frontend/
│   └── src/
│       ├── layouts/AdminLayout.jsx   # Menu lateral del panel
│       ├── pages/Reportar.jsx        # Formulario publico (encuesta) del QR
│       ├── pages/EquipoDetalle.jsx   # QR descargable + historial por maquina
│       ├── pages/Dashboard.jsx, Equipos.jsx, Incidencias.jsx
│       └── api/client.js
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## IMPORTANTE: reinicia la base de datos antes de probar esta version

Se agrego una columna nueva y obligatoria (`tipo_falla`) a la tabla de
incidencias. Como todavia no usamos migraciones (Alembic queda pendiente),
si ya habias levantado el sistema antes, **hay que reiniciar la base de
datos de desarrollo** (solo se pierde la data de prueba):

```bash
cd GymKeep
docker compose down -v   # -v borra el volumen de Postgres (datos de prueba)
docker compose up --build
```

## Como correrlo

### 1) Backend

```bash
cd GymKeep
cp .env.example .env
docker compose up --build
```

API en `http://localhost:8000` (docs en `http://localhost:8000/docs`).

### 2) Frontend

```bash
cd GymKeep/frontend
npm install
cp .env.example .env
npm run dev
```

Panel en `http://localhost:5173`.

### 3) Probar el flujo del QR

1. Crea un equipo desde **Equipamiento**.
2. Haz clic en **Ver detalle** → aparece la imagen del QR.
3. Escanea el QR con el celular (debe estar en la misma red que tu compu, o
   simplemente copia el enlace que aparece bajo el QR y ábrelo en otra pestaña).
4. Se abre el formulario publico: elige un tipo de falla, escribe un nombre y
   envía. La incidencia queda registrada con fecha/hora y prioridad automática,
   visible en **Incidencias** y en el historial del equipo.

## Tests

```bash
cd GymKeep
pytest
```

## Proximos pasos

- Modulo de vision por computadora (YOLOv8/OpenCV) para medir uso real.
- Modulo de costos/repuestos y dashboard financiero (Costo Total de Propiedad).
- Autenticacion para el panel (por ahora de acceso libre, para desarrollo).
- Migrar la creacion de tablas a Alembic (migraciones versionadas), para no
  tener que resetear la base de datos cada vez que cambia el esquema.
- Frontend movil/PWA dedicado para el escaneo de QR.
