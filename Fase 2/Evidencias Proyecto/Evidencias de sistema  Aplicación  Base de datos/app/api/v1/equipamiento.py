import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.crud import equipamiento as crud_equipamiento
from app.schemas.equipamiento import EquipoCreate, EquipoOut, EquipoUpdate

router = APIRouter()


@router.post("/", response_model=EquipoOut, status_code=status.HTTP_201_CREATED)
def crear_equipo(equipo_in: EquipoCreate, db: Session = Depends(get_db)):
    """Registra un nuevo equipo/maquina del gimnasio."""
    existente = crud_equipamiento.get_equipo_by_qr(db, equipo_in.codigo_qr)
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe un equipo con ese codigo QR.")
    return crud_equipamiento.create_equipo(db, equipo_in)


@router.get("/", response_model=list[EquipoOut])
def listar_equipos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lista los equipos registrados, con paginacion simple."""
    return crud_equipamiento.list_equipos(db, skip=skip, limit=limit)


@router.get("/qr/{codigo_qr}", response_model=EquipoOut)
def obtener_equipo_por_qr(codigo_qr: str, db: Session = Depends(get_db)):
    """Obtiene un equipo a partir del codigo QR escaneado (usado por el formulario publico)."""
    equipo = crud_equipamiento.get_equipo_by_qr(db, codigo_qr)
    if not equipo:
        raise HTTPException(status_code=404, detail="No existe un equipo con ese codigo QR.")
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

    url_reporte = f"{settings.frontend_url}/reportar/{equipo.codigo_qr}"
    imagen = qrcode.make(url_reporte)

    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


@router.patch("/{equipo_id}", response_model=EquipoOut)
def actualizar_equipo(equipo_id: int, equipo_in: EquipoUpdate, db: Session = Depends(get_db)):
    """Actualiza datos de un equipo (estado, ubicacion, etc.)."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    return crud_equipamiento.update_equipo(db, equipo, equipo_in)


@router.delete("/{equipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_equipo(equipo_id: int, db: Session = Depends(get_db)):
    """Elimina un equipo del sistema."""
    equipo = crud_equipamiento.get_equipo(db, equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    crud_equipamiento.delete_equipo(db, equipo)
