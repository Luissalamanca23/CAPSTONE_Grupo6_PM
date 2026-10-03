"""Endpoints de integracion del modulo de vision con la plataforma.

Dos consumidores:
- El pipeline de vision (GymKeep/vision): lee la configuracion de cada camara (zonas y
  parametros) y envia su estado en vivo y el ultimo cuadro.
- El panel web: lista maquinas con su tiempo de uso, muestra el historial de cada una, ve
  las camaras en vivo y define/edita las zonas de las maquinas sobre la imagen.

Guia completa: vision/INTEGRACION.md.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.gymkeep import Camara, Equipo
from app.schemas.vision import (
    CamaraVisionDetalle,
    CamaraVisionOut,
    ConfiguracionPipeline,
    EstadoVivoIn,
    EstadoVivoOut,
    MaquinaEnCamara,
    MaquinaUsoDetalle,
    MaquinaUsoResumen,
    ParametrosVision,
    RoiIn,
)
from app.services import vision_service as servicio

router = APIRouter()

MAX_BYTES_IMAGEN = 5 * 1024 * 1024
SIN_CACHE = {"Cache-Control": "no-store"}


def _camara(db: Session, camara_id: int) -> Camara:
    camara = db.get(Camara, camara_id)
    if camara is None:
        raise HTTPException(status_code=404, detail="Camara no encontrada.")
    return camara


def _equipo(db: Session, equipo_id: int) -> Equipo:
    equipo = db.get(Equipo, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    return equipo


async def _leer_imagen(request: Request) -> bytes:
    contenido = await request.body()
    if len(contenido) > MAX_BYTES_IMAGEN:
        raise HTTPException(status_code=413, detail="La imagen supera los 5 MB.")
    return contenido


# ---------------------------------------------------------------- camaras y zonas


@router.get("/camaras", response_model=list[CamaraVisionOut])
def listar_camaras(sucursal_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Camaras con su estado: si el pipeline esta enviando datos (`en_linea`), si hay una
    imagen para mostrar (`tiene_cuadro`) y cuantas maquinas tienen zona definida."""
    return servicio.listar_camaras(db, sucursal_id)


@router.get("/camaras/{camara_id}", response_model=CamaraVisionDetalle)
def obtener_camara(camara_id: int, db: Session = Depends(get_db)):
    """Detalle de una camara: sus maquinas con la zona de cada una (poligono normalizado
    0..1 sobre la imagen) y los parametros de deteccion calibrados para ella."""
    return servicio.detalle_camara(db, _camara(db, camara_id))


@router.put("/camaras/{camara_id}/maquinas/{equipo_id}", response_model=MaquinaEnCamara)
def guardar_zona(camara_id: int, equipo_id: int, roi: RoiIn, db: Session = Depends(get_db)):
    """Crea o reemplaza la zona de una maquina en esta camara (lo que el operador dibuja sobre
    la imagen). La maquina debe ser de la misma sucursal que la camara. Para agregar una
    maquina nueva, crearla antes con POST /equipamiento/ y luego dibujar su zona aqui."""
    camara, equipo = _camara(db, camara_id), _equipo(db, equipo_id)
    if equipo.sucursal_id != camara.sucursal_id:
        raise HTTPException(status_code=400, detail="La maquina y la camara son de sucursales distintas.")
    return servicio.guardar_roi(db, camara, equipo, roi.puntos)


@router.delete("/camaras/{camara_id}/maquinas/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def quitar_zona(camara_id: int, equipo_id: int, db: Session = Depends(get_db)):
    """Quita la maquina de esta camara (el equipo sigue existiendo en el inventario)."""
    if not servicio.quitar_maquina(db, _camara(db, camara_id), equipo_id):
        raise HTTPException(status_code=404, detail="Esa maquina no esta en esta camara.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/camaras/{camara_id}/parametros", response_model=ParametrosVision)
def guardar_parametros(camara_id: int, parametros: ParametrosVision, db: Session = Depends(get_db)):
    """Guarda los parametros de deteccion de esta camara (T_on, T_off, confianza minima,
    gracia, escala de tiempo). El pipeline los toma en su proxima lectura de configuracion."""
    return servicio.guardar_parametros(db, _camara(db, camara_id), parametros)


@router.get("/camaras/{camara_id}/configuracion", response_model=ConfiguracionPipeline)
def configuracion_pipeline(camara_id: int, db: Session = Depends(get_db)):
    """Para el pipeline: maquinas activas con zona y parametros. El pipeline la vuelve a leer
    cada pocos segundos, asi una zona dibujada en el panel se aplica sin reiniciarlo."""
    return servicio.configuracion_pipeline(db, _camara(db, camara_id))


# ---------------------------------------------------------------- en vivo (pipeline -> Mongo)


@router.post("/camaras/{camara_id}/vivo", status_code=status.HTTP_202_ACCEPTED)
def registrar_vivo(camara_id: int, estado: EstadoVivoIn, db: Session = Depends(get_db)):
    """El pipeline informa lo que ve (cada ~1 s): estado de cada maquina y personas
    detectadas. Queda en MongoDB (`camaras_vivo`, `detecciones_raw`, `telemetria_camaras`) y
    actualiza `camaras.ultima_conexion`."""
    servicio.registrar_vivo(db, _camara(db, camara_id), estado)
    return {"ok": True}


@router.get("/camaras/{camara_id}/vivo", response_model=EstadoVivoOut)
def obtener_vivo(camara_id: int, db: Session = Depends(get_db)):
    """Ultimo estado informado por el pipeline (sin la imagen). `en_linea` es falso si no
    llegan datos hace mas de 15 s."""
    _camara(db, camara_id)
    return servicio.estado_vivo(camara_id)


@router.put("/camaras/{camara_id}/cuadro", status_code=status.HTTP_201_CREATED)
async def subir_cuadro(camara_id: int, request: Request, db: Session = Depends(get_db)):
    """Ultima imagen de la camara (cuerpo = JPEG o PNG). La envia el pipeline cada pocos
    segundos con las cabezas ya difuminadas; tambien sirve para subir una imagen de
    referencia y dibujar las zonas antes de tener el pipeline corriendo."""
    camara = _camara(db, camara_id)
    try:
        return servicio.guardar_cuadro(camara, await _leer_imagen(request))
    except servicio.ImagenInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/camaras/{camara_id}/cuadro", response_class=Response)
def obtener_cuadro(camara_id: int, db: Session = Depends(get_db)):
    """Ultima imagen de la camara (JPEG)."""
    _camara(db, camara_id)
    contenido = servicio.leer_cuadro(camara_id)
    if contenido is None:
        raise HTTPException(status_code=404, detail="Esta camara todavia no tiene imagen.")
    return Response(content=contenido, media_type="image/jpeg", headers=SIN_CACHE)


# ---------------------------------------------------------------- uso de maquinas


@router.get("/maquinas", response_model=list[MaquinaUsoResumen])
def listar_maquinas(sucursal_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Maquinas con su tiempo de uso (horometro), uso de los ultimos 7 dias, horas desde la
    ultima mantencion, si una camara la mide y si esta en uso ahora mismo."""
    return servicio.resumen_maquinas(db, sucursal_id)


@router.get("/maquinas/{equipo_id}", response_model=MaquinaUsoDetalle)
def obtener_maquina(equipo_id: int, db: Session = Depends(get_db)):
    """Historial completo de una maquina en una sola llamada: resumen de uso, uso diario de
    los ultimos 30 dias, sesiones de uso, incidencias y mantenciones."""
    return servicio.detalle_maquina(db, _equipo(db, equipo_id))


@router.get("/maquinas/{equipo_id}/foto", response_class=Response)
def obtener_foto(equipo_id: int, db: Session = Depends(get_db)):
    """Foto de referencia de la maquina (JPEG)."""
    _equipo(db, equipo_id)
    contenido = servicio.leer_foto(equipo_id)
    if contenido is None:
        raise HTTPException(status_code=404, detail="La maquina no tiene foto.")
    return Response(content=contenido, media_type="image/jpeg", headers=SIN_CACHE)


@router.put("/maquinas/{equipo_id}/foto", status_code=status.HTTP_201_CREATED)
async def subir_foto(equipo_id: int, request: Request, db: Session = Depends(get_db)):
    """Sube la foto de referencia (cuerpo = JPEG o PNG)."""
    _equipo(db, equipo_id)
    try:
        return servicio.guardar_foto(equipo_id, await _leer_imagen(request), origen="subida")
    except servicio.ImagenInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/maquinas/{equipo_id}/foto/desde-camara", status_code=status.HTTP_201_CREATED)
def foto_desde_camara(equipo_id: int, camara_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Toma la foto de referencia recortando la zona de la maquina del ultimo cuadro de la
    camara (o de `camara_id`, si la mira mas de una)."""
    try:
        return servicio.foto_desde_camara(db, _equipo(db, equipo_id), camara_id)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
