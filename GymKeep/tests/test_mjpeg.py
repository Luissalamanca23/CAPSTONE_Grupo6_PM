"""Flujo MJPEG: formato de cada parte, entrega solo de cuadros nuevos y corte al desconectarse."""

import asyncio

from app.services import mjpeg


def correr(corrutina):
    return asyncio.run(corrutina)


async def juntar(generador):
    return [parte async for parte in generador]


def test_parte_tiene_cabeceras_y_largo():
    jpeg = b"\xff\xd8abc"
    p = mjpeg.parte(jpeg)
    assert p.startswith(b"--gymkeepframe\r\nContent-Type: image/jpeg\r\nContent-Length: 5\r\n\r\n")
    assert p.endswith(jpeg + b"\r\n")


def test_entrega_cada_cuadro_nuevo_una_sola_vez():
    cuadros = {"actual": (1, b"A")}
    llamadas = []

    def lector(camara_id, desde):
        llamadas.append(desde)
        marca, jpeg = cuadros["actual"]
        return None if marca == desde else (marca, jpeg)

    async def prueba():
        salida = []
        generador = mjpeg.flujo(7, lector, cada_s=0.01, repetir_cada_s=99, max_s=0.3)
        async for p in generador:
            salida.append(p)
            if len(salida) == 1:
                cuadros["actual"] = (2, b"B")  # llega un cuadro nuevo
        return salida

    salida = correr(prueba())
    assert [p.endswith(b"A\r\n") or p.endswith(b"B\r\n") for p in salida] == [True, True]
    assert salida[0].endswith(b"A\r\n") and salida[1].endswith(b"B\r\n")
    assert llamadas[0] is None and 1 in llamadas


def test_se_detiene_cuando_el_cliente_se_desconecta():
    async def desconectado():
        return True

    salida = correr(juntar(mjpeg.flujo(1, lambda c, d: (1, b"X"), cada_s=0.01, desconectado=desconectado)))
    assert salida == []


def test_reenvia_el_ultimo_cuadro_si_pasa_mucho_sin_novedades():
    estado = {"entregado": False}

    def lector(camara_id, desde):
        if estado["entregado"]:
            return None
        estado["entregado"] = True
        return 1, b"Z"

    salida = correr(juntar(mjpeg.flujo(1, lector, cada_s=0.01, repetir_cada_s=0.05, max_s=0.3)))
    assert len(salida) >= 2 and all(p.endswith(b"Z\r\n") for p in salida)
