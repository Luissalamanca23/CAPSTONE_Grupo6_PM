from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import camara as crud_camara
from app.schemas.camara import CamaraCreate, CamaraOut
from app.services import eliminacion

router = APIRouter()


@router.get("/", response_model=list[CamaraOut])
def listar_camaras(
    sucursal_id: Optional[int] = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
):
    """Camaras desplegadas en una sucursal y su asociacion a equipos. La deteccion de uso
    la hace el modulo de vision (GymKeep/vision/), que registra sus camaras aqui."""
    return crud_camara.list_camaras(db, sucursal_id=sucursal_id, skip=skip, limit=limit)


@router.post("/", response_model=CamaraOut, status_code=status.HTTP_201_CREATED)
def crear_camara(camara_in: CamaraCreate, db: Session = Depends(get_db)):
    return crud_camara.create_camara(db, camara_in)


@router.get("/{camara_id}/resumen-eliminacion")
def resumen_eliminacion_camara(camara_id: int, db: Session = Depends(get_db)):
    camara = crud_camara.get_camara(db, camara_id)
    if not camara:
        raise HTTPException(status_code=404, detail="Camara no encontrada.")
    return eliminacion.respuesta_resumen("camara", camara.nombre, eliminacion.resumen_camara(db, camara_id))


@router.delete("/{camara_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_camara(camara_id: int, forzar: bool = Query(False), db: Session = Depends(get_db)):
    """Elimina la camara con sus eventos IA y su estado en vivo. Las sesiones de uso y los
    reportes que la mencionaban se conservan, sin camara. Con datos exige `forzar=true`."""
    camara = crud_camara.get_camara(db, camara_id)
    if not camara:
        raise HTTPException(status_code=404, detail="Camara no encontrada.")
    if not forzar and sum(eliminacion.resumen_camara(db, camara_id).values()):
        raise HTTPException(status_code=400, detail="La camara tiene datos asociados; confirme la eliminacion (forzar=true).")
    eliminacion.eliminar_camara(db, camara_id)
