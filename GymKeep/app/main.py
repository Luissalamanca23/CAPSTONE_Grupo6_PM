from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.project_name)

# El Portal de Reporte Express (formulario del QR) lo puede abrir cualquier persona,
# desde cualquier red (celular por datos moviles, tunel publico, etc.), y esta API no
# usa cookies/sesion (no hay login todavia) -- por eso se permite cualquier origen.
# allow_credentials=False es lo que hace valido usar "*" segun la especificacion CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto el navegador recibe el header pero JS no puede leerlo (lo bloquea el CORS
    # por defecto): el listado de incidencias lo usa para saber el total y armar la
    # paginacion sin traer todos los registros de una vez.
    expose_headers=["X-Total-Count"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
def health_check():
    """Endpoint simple para verificar que la API esta viva."""
    return {"status": "ok", "project": settings.project_name}
