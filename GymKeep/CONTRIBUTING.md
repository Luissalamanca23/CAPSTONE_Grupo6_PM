# Cómo trabajar en GymKeep (guía para el equipo)

Esta guía es para cualquiera del equipo que vaya a levantar el sistema o
modificar código. Para el detalle técnico completo (estructura, endpoints,
esquema de base de datos, etc.) revisa `README.md` en esta misma carpeta.

## 1. Requisitos antes de levantar el sistema

Instala esto antes de partir (una sola vez por computador):

- **Git** — para bajar/subir el código.
- **Docker Desktop** — corre el backend (API), PostgreSQL, MongoDB y MinIO.
  Descárgalo en docker.com/products/docker-desktop y déjalo abierto mientras
  trabajas.
- **Node.js 18 o superior** (incluye `npm`) — corre el panel web (frontend).
  Descárgalo en nodejs.org (versión LTS).

No hace falta instalar Python, Postgres ni Mongo a mano: Docker se encarga de eso.

## 2. Bajar el proyecto por primera vez

```bash
git clone https://github.com/Luissalamanca23/CAPSTONE_Grupo6_PM.git
cd CAPSTONE_Grupo6_PM/GymKeep
```

Si ya lo tenías clonado, solo actualiza:

```bash
git checkout main
git pull origin main
```

## 3. Levantar el sistema

**Backend** (en una terminal, desde `GymKeep`):

```bash
cp .env.example .env
docker compose up --build
```

Déjala corriendo. Esto levanta 4 contenedores: PostgreSQL, MongoDB, MinIO y la API.
La API queda en `http://localhost:8000/docs`.

**Frontend** (en otra terminal, desde `GymKeep/frontend`):

```bash
npm install
cp .env.example .env
npm run dev
```

Panel en `http://localhost:5173`.

### Si ya tenías el sistema levantado con la version anterior (antes de la base de datos ampliada)

El esquema de base de datos cambió de forma importante: se agregaron
empresas/sucursales/zonas, el QR pasó a ser su propia tabla (`qr_equipos`, ya no una
columna de `equipos`), y el tipo de falla pasó de ser un valor fijo a un catálogo
(`tipos_falla`). Como todavía estamos en desarrollo (solo hay datos de prueba), la forma
de actualizar es reiniciar los volúmenes y dejar que se cargue el esquema nuevo:

```bash
docker compose down -v   # -v borra los datos de prueba de Postgres/Mongo/MinIO
docker compose up --build
```

También hay que actualizar las dependencias de Python (se agregaron `pymongo` y
`boto3`) si vas a correr algo fuera de Docker (por ejemplo los tests):

```bash
pip install -r requirements.txt
```

### Si ya lo tenías levantado y bajaste cambios nuevos (en general)

Si alguien del equipo modificó el modelo de datos (agregó una columna, una
tabla, etc.), hay que reiniciar la base de datos de desarrollo para que
tome el nuevo esquema (se pierde solo la data de prueba, no el código):

```bash
docker compose down -v
docker compose up --build
```

Si no estás seguro si hace falta, hazlo igual — no rompe nada.

## 4. Si vas a modificar algo

Para no pisarnos el trabajo entre los tres:

1. Antes de empezar, trae lo último: `git pull origin main`
2. Trabaja en una rama con un nombre corto que describa el cambio:
   ```bash
   git checkout -b modulo-vision-computadora
   ```
3. Haz commits chicos y con mensajes claros:
   ```bash
   git add .
   git commit -m "Agrega endpoint de..."
   ```
4. Sube tu rama:
   ```bash
   git push origin modulo-vision-computadora
   ```
5. Avisa al equipo (o abre un Pull Request en GitHub) antes de mezclar a
   `main`, así revisamos entre todos que no se rompa nada.

Si el cambio es chico (typo, ajuste menor) está bien trabajar directo en
`main`, pero para módulos nuevos o cambios grandes mejor usar una rama.

### Dónde va cada cosa nueva (mapa rápido del esquema ampliado)

- Nueva sucursal/zona/empresa → `app/models/gymkeep.py` + endpoints en
  `app/api/v1/empresas.py`, `sucursales.py`, `zonas.py`.
- Cambios al equipamiento o al QR → `app/models/gymkeep.py` (`Equipo`, `QrEquipo`),
  `app/crud/equipamiento.py`, `app/api/v1/equipamiento.py`.
- Nuevo tipo de falla → se agrega como fila en `postgres/schema.sql` (tabla
  `tipos_falla`, sección de seed), no como código nuevo.
- Cambios a incidencias → `app/crud/incidencia.py`, `app/api/v1/incidencias.py`.
- Módulo de cámaras/IA (futuro) → `app/models/gymkeep.py` (`Camara`, `ModeloIA`,
  `EventoIAResumen`, `SesionUso`), `app/services/ai_event_service.py`,
  `app/api/v1/camaras.py` / `modelos_ia.py` / `eventos_ia.py`, y las colecciones de
  Mongo en `mongo/init-mongo.js`. Ver `GymKeep_BDD_Completa/README.md` para el diseño
  completo (todavía no hay pipeline de visión por computadora conectado).

## 5. Qué NO se debe subir a git

Ya está en `.gitignore`, pero por si acaso nunca subas manualmente:

- `node_modules/` (se regenera con `npm install`)
- `.env` (configuración local de cada uno)
- `__pycache__/`, `*.pyc`
- Las carpetas de datos de Postgres/Mongo/MinIO (`db_data`, `mongo_data`, `minio_data`)

## 6. Dudas / algo no corre

Copia el mensaje de error exacto (de la terminal o de la consola del
navegador, F12) y compártelo en el grupo antes de intentar arreglarlo a
ciegas — la mayoría de los problemas son de configuración (`.env`,
contenedores no reiniciados, `pip install -r requirements.txt` desactualizado)
y se resuelven rápido si se ve el error real.
