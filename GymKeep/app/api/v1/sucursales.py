from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import sucursal as crud_sucursal
from app.schemas.sucursal import SucursalCreate, SucursalOut

router = APIRouter()


@router.get("/", response_model=list[SucursalOut])
def listar_sucursales(
    empresa_id: Optional[int] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Lista las sucursales (sedes) de una empresa. El equipamiento y las camaras se
    registran siempre dentro de una sucursal."""
    return crud_sucursal.list_sucursales(db, empresa_id=empresa_id, skip=skip, limit=limit)


@router.post("/", response_model=SucursalOut, status_code=status.HTTP_201_CREATED)
def crear_sucursal(sucursal_in: SucursalCreate, db: Session = Depends(get_db)):
    return crud_sucursal.create_sucursal(db, sucursal_in)
