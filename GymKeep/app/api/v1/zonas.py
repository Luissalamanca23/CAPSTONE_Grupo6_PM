from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import zona as crud_zona
from app.schemas.zona import ZonaCreate, ZonaOut
from app.services import eliminacion

router = APIRouter()


@router.get("/", response_model=list[ZonaOut])
def listar_zonas(
    sucursal_id: Optional[int] = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
):
    """Lista las zonas (cardio, musculacion, funcional, etc.) de una sucursal."""
    return crud_zona.list_zonas(db, sucursal_id=sucursal_id, skip=skip, limit=limit)


@router.post("/", response_model=ZonaOut, status_code=status.HTTP_201_CREATED)
def crear_zona(zona_in: ZonaCreate, db: Session = Depends(get_db)):
    return crud_zona.create_zona(db, zona_in)


@router.get("/{zona_id}/resumen-eliminacion")
def resumen_eliminacion_zona(zona_id: int, db: Session = Depends(get_db)):
    zona = crud_zona.get_zona(db, zona_id)
    if not zona:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")
    return eliminacion.respuesta_resumen("zona", zona.nombre, eliminacion.resumen_zona(db, zona_id))


@router.delete("/{zona_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_zona(zona_id: int, db: Session = Depends(get_db)):
    """Elimina la zona. Sus maquinas y camaras NO se borran: quedan sin zona asignada."""
    if not crud_zona.get_zona(db, zona_id):
        raise HTTPException(status_code=404, detail="Zona no encontrada.")
    eliminacion.eliminar_zona(db, zona_id)
