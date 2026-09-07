# Cómo trabajar en GymKeep (guía para el equipo)

Esta guía es para cualquiera del equipo que vaya a levantar el sistema o
modificar código. Para el detalle técnico completo (estructura, endpoints,
etc.) revisa `README.md` en esta misma carpeta.

## 1. Requisitos antes de levantar el sistema

Instala esto antes de partir (una sola vez por computador):

- **Git** — para bajar/subir el código.
- **Docker Desktop** — corre el backend (API) y la base de datos Postgres.
  Descárgalo en docker.com/products/docker-desktop y déjalo abierto mientras
  trabajas.
- **Node.js 18 o superior** (incluye `npm`) — corre el panel web (frontend).
  Descárgalo en nodejs.org (versión LTS).

No hace falta instalar Python ni Postgres a mano: Docker se encarga de eso.

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

Déjala corriendo. La API queda en `http://localhost:8000/docs`.

**Frontend** (en otra terminal, desde `GymKeep/frontend`):

```bash
npm install
cp .env.example .env
npm run dev
```

Panel en `http://localhost:5173`.

### Si ya lo tenías levantado y bajaste cambios nuevos

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

## 5. Qué NO se debe subir a git

Ya está en `.gitignore`, pero por si acaso nunca subas manualmente:

- `node_modules/` (se regenera con `npm install`)
- `.env` (configuración local de cada uno)
- `__pycache__/`, `*.pyc`
- La carpeta de datos de Postgres (`db_data`)

## 6. Dudas / algo no corre

Copia el mensaje de error exacto (de la terminal o de la consola del
navegador, F12) y compártelo en el grupo antes de intentar arreglarlo a
ciegas — la mayoría de los problemas son de configuración (`.env`,
contenedores no reiniciados) y se resuelven rápido si se ve el error real.
