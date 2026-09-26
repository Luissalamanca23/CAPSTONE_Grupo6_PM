from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import camara as crud_camara
from app.schemas.camara import CamaraCreate, CamaraOut

router = APIRouter()


@router.get("/", response_model=list[CamaraOut])
def listar_camaras(
    sucursal_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Camaras desplegadas en una sucursal y su asociacion a equipos. La deteccion de uso
    la hace el modulo de vision (GymKeep/vision/), que registra sus camaras aqui."""
    return crud_camara.list_camaras(db, sucursal_id=sucursal_id, skip=skip, limit=limit)


@router.post("/", response_model=CamaraOut, status_code=status.HTTP_201_CREATED)
def crear_camara(camara_in: CamaraCreate, db: Session = Depends(get_db)):
    return crud_camara.create_camara(db, camara_in)
