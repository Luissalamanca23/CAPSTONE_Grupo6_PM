# GymKeep — Base de datos completa

Este paquete amplía la base actual del Capstone para soportar un sistema real de
gestión de equipamiento en gimnasios con **PostgreSQL + MongoDB + almacenamiento
de evidencia de cámara**.

## 1. Arquitectura

```text
EMPRESA
  └── SUCURSAL
       ├── ZONA
       │    ├── CAMARA
       │    └── EQUIPO
       │         ├── QR
       │         ├── INCIDENCIA ── TIPO_FALLA
       │         │     └── MANTENIMIENTO
       │         └── SESION_USO
       │
       └──────────────────────────────┐
                                      │
                                  MongoDB
                                      │
                                EVENTOS IA
                                      │
                        detecciones / tracking
                                      │
                             snapshot / clip
                                      │
                                MinIO / S3
```

## 2. Qué se guarda en cada sistema

### PostgreSQL

Es la **fuente oficial del negocio**:

- empresas;
- sucursales;
- zonas;
- equipos;
- QR históricos;
- cámaras;
- relación cámara/equipo y ROI;
- modelos/versiones de IA;
- catálogo de fallas;
- incidencias;
- mantenimientos;
- sesiones de uso consolidadas;
- resumen/index de eventos IA;
- auditoría.

### MongoDB

Se usa para información flexible y de mayor volumen producida por visión
computacional:

- `eventos_ia`: eventos semánticos importantes;
- `detecciones_raw`: detecciones temporales para depuración/calibración;
- `telemetria_camaras`: FPS, latencia, temperatura, frames perdidos, etc.

`detecciones_raw` usa un TTL de 7 días y `telemetria_camaras` un TTL de 30 días.

### MinIO / S3

Las imágenes y clips **no deben almacenarse como blobs en PostgreSQL o MongoDB**.
Se guardan en almacenamiento de objetos y las bases mantienen solamente la URL.

## 3. Tablas PostgreSQL

| Tabla | Responsabilidad |
|---|---|
| `empresas` | Cliente/organización |
| `sucursales` | Sedes de la empresa |
| `zonas` | Cardio, musculación, funcional, etc. |
| `equipos` | Activo físico |
| `qr_equipos` | Historial de QR del equipo |
| `camaras` | Cámara desplegada en una sucursal |
| `camara_equipos` | Qué equipos observa cada cámara y su ROI |
| `modelos_ia` | Versionado del modelo de IA |
| `tipos_falla` | Catálogo administrable de fallas |
| `incidencias` | Fallas reportadas por QR, IA, técnico o sistema |
| `mantenimientos` | Intervenciones realizadas |
| `sesiones_uso` | Uso consolidado de un equipo |
| `eventos_ia_resumen` | Puente PostgreSQL ↔ MongoDB |
| `registros_auditoria` | Registro de operaciones importantes |

## 4. Concepto clave: detección != uso

Una cámara podría detectar a la misma persona en 500 frames.

Eso **no son 500 usos**.

El pipeline debe consolidar:

```text
detecciones consecutivas
       ↓
tracking de persona/equipo
       ↓
reglas temporales
       ↓
inicio_uso
       ↓
sesión abierta
       ↓
fin_uso
       ↓
sesión cerrada
```

Ejemplo final:

```text
Equipo: Cinta de correr 01
Inicio: 17:30:01
Fin:    17:42:30
Uso:    749 segundos
Origen: IA
Confianza promedio: 94 %
```

Ese resultado vive en `sesiones_uso`.

Los eventos que justifican el resultado viven en MongoDB.

## 5. Flujo de una incidencia QR

```text
QR activo
  ↓
/reportar/{token}
  ↓
usuario elige tipo de falla
  ↓
incidencias.origen = "qr"
  ↓
tipo_falla.prioridad_base
  ↓
cola de mantenimiento
```

El QR se separa del equipo para permitir **revocación, reimpresión e historial**.

## 6. Flujo de una incidencia detectada por IA

```text
Cámara
  ↓
Modelo IA
  ↓
evento "posible_falla"
  ↓
MongoDB eventos_ia
  ↓
eventos_ia_resumen
  ↓
regla/umbral
  ↓
incidencias.origen = "ia"
```

## 7. Instalación local

Copiar:

```bash
cp .env.example .env
```

Levantar infraestructura:

```bash
docker compose -f docker-compose.bdd.yml up -d
```

Servicios:

- PostgreSQL: `localhost:5432`
- MongoDB: `localhost:27017`
- MinIO API: `localhost:9000`
- MinIO consola: `localhost:9001`

El contenedor PostgreSQL carga automáticamente:

```text
postgres/schema.sql
postgres/seed.sql
```

MongoDB carga:

```text
mongo/init-mongo.js
```

## 8. Dependencias Python

Agregar a `requirements.txt`:

```text
pymongo==4.10.1
boto3==1.35.36
```

Ya se utiliza SQLAlchemy/PostgreSQL/Alembic en el proyecto existente.

## 9. Integración con FastAPI

Copiar o adaptar:

```text
app/core/config.py
app/core/database.py
app/core/mongo.py
app/models/gymkeep.py
app/models/__init__.py
app/schemas/ai_event.py
app/services/ai_event_service.py
```

El archivo `gymkeep.py` está concentrado para que sea fácil revisar el modelo.
Después puede separarse en múltiples archivos sin cambiar el diseño.

## 10. Alembic

El paquete contiene:

```text
alembic/versions/0001_gymkeep_ampliado.py
```

Para un proyecto nuevo se puede usar directamente el `schema.sql`.

Para migrar la base actual **con datos que quieran conservar**, no se recomienda
borrarla. Hay que crear una migración intermedia que:

1. cree empresa/sucursal/zona;
2. asigne los equipos existentes a una sucursal;
3. copie `equipos.codigo_qr` a `qr_equipos.token` o genere nuevos UUID;
4. migre las incidencias existentes al catálogo `tipos_falla`;
5. elimine las columnas antiguas solo al final.

## 11. Consultas útiles

### Uso diario por equipo

```sql
SELECT *
FROM vw_uso_diario_equipos
WHERE equipo_id = 1
ORDER BY fecha DESC;
```

### Equipos con urgencias abiertas

```sql
SELECT *
FROM vw_estado_equipos
WHERE urgentes_abiertas > 0;
```

### Suma de horas de uso por sucursal

```sql
SELECT
    s.nombre AS sucursal,
    ROUND(SUM(u.duracion_segundos) / 3600.0, 2) AS horas_uso
FROM sesiones_uso u
JOIN equipos e ON e.id = u.equipo_id
JOIN sucursales s ON s.id = e.sucursal_id
WHERE u.estado = 'cerrada'
GROUP BY s.id, s.nombre
ORDER BY horas_uso DESC;
```

### Fallas por equipo

```sql
SELECT
    e.nombre,
    tf.nombre AS falla,
    COUNT(*) AS cantidad
FROM incidencias i
JOIN equipos e ON e.id = i.equipo_id
JOIN tipos_falla tf ON tf.id = i.tipo_falla_id
GROUP BY e.id, e.nombre, tf.id, tf.nombre
ORDER BY cantidad DESC;
```

## 12. Archivos del paquete

```text
GymKeep_BDD_Completa/
├── README.md
├── INTEGRACION_REPO_ACTUAL.md
├── .env.example
├── docker-compose.bdd.yml
├── requirements-bdd.txt
├── postgres/
│   ├── schema.sql
│   └── seed.sql
├── mongo/
│   └── init-mongo.js
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── mongo.py
│   │   └── storage.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── gymkeep.py
│   ├── schemas/
│   │   └── ai_event.py
│   └── services/
│       └── ai_event_service.py
├── alembic/
│   └── versions/
│       └── 0001_gymkeep_ampliado.py
└── examples/
    └── evento_inicio_uso.json
```


## 13. Nota sobre el backend actual

Lee `INTEGRACION_REPO_ACTUAL.md` antes de reemplazar los modelos existentes.
El esquema nuevo normaliza QR y tipos de falla, por lo que los endpoints actuales
deben adaptarse. Para el estado actual del Capstone se recomienda una base de
desarrollo nueva y migrar la lógica del API por módulos.
