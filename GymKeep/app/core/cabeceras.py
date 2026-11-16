"""Cabeceras de seguridad para todas las respuestas de la API.

Es un middleware ASGI puro (no BaseHTTPMiddleware) para no interferir con las respuestas en
streaming del video de las camaras.
"""

CABECERAS_BASE = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"same-origin"),
]


class CabecerasSeguridad:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Lo que tiene que ver con sesiones nunca debe quedar en la cache del navegador o de un proxy.
        sin_cache = scope.get("path", "").startswith("/api/v1/auth")

        async def enviar(mensaje):
            if mensaje["type"] == "http.response.start":
                cabeceras = list(mensaje.get("headers", []))
                presentes = {nombre.lower() for nombre, _ in cabeceras}
                for nombre, valor in CABECERAS_BASE:
                    if nombre not in presentes:
                        cabeceras.append((nombre, valor))
                if sin_cache and b"cache-control" not in presentes:
                    cabeceras.append((b"cache-control", b"no-store"))
                mensaje = {**mensaje, "headers": cabeceras}
            await send(mensaje)

        await self.app(scope, receive, enviar)
