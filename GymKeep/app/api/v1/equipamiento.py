import io
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.crud import equipamiento as crud_equipamiento
from app.crud import sucursal as crud_sucursal
from app.crud import zona as crud_zona
from app.schemas.equipamiento import EquipoCreate, EquipoOut, EquipoUpdate, QrEquipoOut

router = APIRouter()


@router.post("/", response_model=EquipoOut, status_code=status.HTTP_201_CREATED)
def crear_equipo(equipo_in: EquipoCreate, db: Session = Depends(get_db)):
    """Registra un nuevo equipo/maquina del gimnasio dentro de una sucursal (y opcionalmente
    una zona). Al crearlo, el backend le emite automaticamente su primer QR activo."""
    sucursal = crud_sucursal.get_sucursal(db, equipo_in.sucursal_id)
    if not sucursal:
        raise HTTPException(status_code=404, detail="La sucursal indicada no existe.")

    if equipo_in.zona_id is not None:
        zona = crud_zona.get_zona(db, equipo_in.zona_id)
        if not zona or zona.sucursal_id != equipo_in.sucursal_id:
            raise HTTPException(status_code=404, detail="La zona indicada no existe en esa sucursal.")

    existente = crud_equipamiento.get_equipo_by_codigo_activo(
        db, equipo_in.sucursal_id, equipo_in.codigo_activo
    )
    if existente:
        raise HTTPException(
            status_code=400, detail="Ya existe un equipo con ese codigo de activo en esta sucursal."
        )

    return crud_equipamiento.create_equipo(db, equipo_in)


@router.get("/", response_model=list[EquipoOut])
def listar_equipos(
    sucursal_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Lista los equipos registrados, con paginacion simple y filtro opcional por sucursal."""
    return crud_equipamiento.list_equipos(db, skip=skip, limit=limit, sucursal_id=sucursal_id)


@router.get("/qr/{token}", response_model=EquipoOut)
def obtener_equipo_por_qr(token: str, db: Session = Depends(get_db)):
    """Obtiene un equipo a partir del token del QR escaneado (usado por el formulario publico).
    Solo resuelve QR activos y no expirados."""
    equipo = crud_equipamiento.get_equipo_by_token(db, token)
    if not equipo:
        raise HTTPException(status_code=404, detail="El codigo QR no es valido o ya no esta activo.")
    return equipo


@router.get("/{equipo_id}", response_model=EquipoOut)
def obtener_equipo(equipo_id: int, db: Session = Depends(get_db)):
    """Obtiene el detalle de un equipo por su id."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    return equipo


@router.get("/{equipo_id}/codigo-qr")
def generar_codigo_qr(equipo_id: int, db: Session = Depends(get_db)):
    """Genera la imagen QR que, al escanearse, abre el formulario publico de reporte de
    fallas para este equipo. Pensada para imprimir y pegar en la maquina."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    qr_activo = equipo.qr_activo
    if not qr_activo:
        raise HTTPException(status_code=404, detail="Este equipo no tiene un QR activo.")

    url_reporte = f"{settings.frontend_url}/reportar/{qr_activo.token}"
    imagen = qrcode.make(url_reporte)

    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


@router.post("/{equipo_id}/regenerar-qr", response_model=QrEquipoOut, status_code=status.HTTP_201_CREATED)
def regenerar_codigo_qr(equipo_id: int, db: Session = Depends(get_db)):
    """Revoca el QR activo del equipo (si existe) y emite uno nuevo. Util si se perdio,
    daño o quiere invalidarse el sticker impreso, sin perder el historial de QR anteriores."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    return crud_equipamiento.regenerar_qr(db, equipo)


@router.patch("/{equipo_id}", response_model=EquipoOut)
def actualizar_equipo(equipo_id: int, equipo_in: EquipoUpdate, db: Session = Depends(get_db)):
    """Actualiza datos de un equipo (estado, zona, etc.)."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    if equipo_in.zona_id is not None:
        zona = crud_zona.get_zona(db, equipo_in.zona_id)
        if not zona or zona.sucursal_id != equipo.sucursal_id:
            raise HTTPException(status_code=404, detail="La zona indicada no existe en esa sucursal.")

    return crud_equipamiento.update_equipo(db, equipo, equipo_in)


@router.delete("/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_equipo(equipo_id: int, db: Session = Depends(get_db)):
    """Elimina un equipo del sistema (junto con su historial de QR). Si el equipo ya tiene
    incidencias reportadas no se puede eliminar (se conserva por auditoria): marquelo como
    'retirado' en su lugar con PATCH."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    if crud_equipamiento.tiene_incidencias(db, equipo):
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar un equipo con incidencias registradas. "
            "Cambie su estado a 'retirado' en su lugar.",
        )
    crud_equipamiento.delete_equipo(db, equipo)
