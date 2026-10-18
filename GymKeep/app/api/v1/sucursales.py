from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import sucursal as crud_sucursal
from app.schemas.sucursal import SucursalCreate, SucursalOut
from app.services import eliminacion

router = APIRouter()


@router.get("/", response_model=list[SucursalOut])
def listar_sucursales(
    empresa_id: Optional[int] = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)
):
    """Lista las sucursales (sedes) de una empresa. El equipamiento y las camaras se
    registran siempre dentro de una sucursal."""
    return crud_sucursal.list_sucursales(db, empresa_id=empresa_id, skip=skip, limit=limit)


@router.post("/", response_model=SucursalOut, status_code=status.HTTP_201_CREATED)
def crear_sucursal(sucursal_in: SucursalCreate, db: Session = Depends(get_db)):
    return crud_sucursal.create_sucursal(db, sucursal_in)


@router.get("/{sucursal_id}/resumen-eliminacion")
def resumen_eliminacion_sucursal(sucursal_id: int, db: Session = Depends(get_db)):
    """Que se borraria junto con la sucursal (para el dialogo de confirmacion del panel)."""
    sucursal = crud_sucursal.get_sucursal(db, sucursal_id)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")
    return eliminacion.respuesta_resumen("sucursal", sucursal.nombre, eliminacion.resumen_sucursal(db, sucursal_id))


@router.delete("/{sucursal_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_sucursal(sucursal_id: int, forzar: bool = Query(False), db: Session = Depends(get_db)):
    """Elimina la sucursal con sus zonas, maquinas, camaras, reportes, mantenimientos y
    sesiones de uso. Si tiene datos, exige `forzar=true` (el panel lo envia tras confirmar)."""
    sucursal = crud_sucursal.get_sucursal(db, sucursal_id)
    if not sucursal:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")
    if not forzar and sum(eliminacion.resumen_sucursal(db, sucursal_id).values()):
        raise HTTPException(status_code=400, detail="La sucursal tiene datos asociados; confirme la eliminacion en cascada (forzar=true).")
    eliminacion.eliminar_sucursal(db, sucursal_id)
