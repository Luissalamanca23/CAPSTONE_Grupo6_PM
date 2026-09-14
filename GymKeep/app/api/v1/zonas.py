from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import zona as crud_zona
from app.schemas.zona import ZonaCreate, ZonaOut

router = APIRouter()


@router.get("/", response_model=list[ZonaOut])
def listar_zonas(
    sucursal_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Lista las zonas (cardio, musculacion, funcional, etc.) de una sucursal."""
    return crud_zona.list_zonas(db, sucursal_id=sucursal_id, skip=skip, limit=limit)


@router.post("/", response_model=ZonaOut, status_code=status.HTTP_201_CREATED)
def crear_zona(zona_in: ZonaCreate, db: Session = Depends(get_db)):
    return crud_zona.create_zona(db, zona_in)
