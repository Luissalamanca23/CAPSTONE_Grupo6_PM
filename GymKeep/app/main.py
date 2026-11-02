import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core import watchdog
from app.core.arranque import asegurar_tablas
from app.core.config import settings
from app.core.origenes import ORIGEN_LOCAL_RE, origenes_permitidos


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    asegurar_tablas()
    tarea = watchdog.iniciar()
    try:
        yield
    finally:
        if tarea is not None:
            tarea.cancel()


app = FastAPI(title=settings.project_name, lifespan=lifespan)

# La sesion va en una cookie HttpOnly, asi que CORS ya no puede ser "*": solo se aceptan los
# origenes del panel (localhost, redes privadas y Tailscale, FRONTEND_URL y CORS_ORIGINS).
# Normalmente el panel y la API comparten dominio y CORS ni se usa.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos(),
    allow_origin_regex=ORIGEN_LOCAL_RE,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto JS no puede leer estos headers: X-Total-Count arma la paginacion de incidencias
    # y WWW-Authenticate distingue una sesion vencida de un PIN incorrecto.
    expose_headers=["X-Total-Count", "WWW-Authenticate"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
def health_check():
    """Endpoint simple para verificar que la API esta viva."""
    return {"status": "ok", "project": settings.project_name}
