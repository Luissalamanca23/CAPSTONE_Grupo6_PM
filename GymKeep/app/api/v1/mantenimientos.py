from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import equipamiento as crud_equipamiento
from app.crud import mantenimiento as crud_mantenimiento
from app.schemas.mantenimiento import MantenimientoCreate, MantenimientoOut

router = APIRouter()


@router.get("/", response_model=list[MantenimientoOut])
def listar_mantenimientos(
    equipo_id: Optional[int] = None,
    tipo: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Historial de mantenimientos, mas reciente primero. Con `equipo_id` queda acotado a un
    equipo (detalle de equipo); sin el, devuelve el historial completo del gimnasio, con
    filtros opcionales de tipo/fecha/texto (vista de Costos de mantencion)."""
    return crud_mantenimiento.listar_mantenimientos(
        db, equipo_id=equipo_id, tipo=tipo, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta, q=q
    )


@router.post("/", response_model=list[MantenimientoOut], status_code=status.HTTP_201_CREATED)
def crear_mantenimiento(mantenimiento_in: MantenimientoCreate, db: Session = Depends(get_db)):
    """Registra un mantenimiento ya realizado (panel de tecnicos). Si trae `incidencia_ids`,
    esas incidencias del equipo quedan marcadas como resueltas; el estado del propio equipo
    NO cambia automaticamente aqui (el tecnico lo confirma aparte, ver PATCH /equipamiento)."""
    equipo = crud_equipamiento.get_equipo(db, mantenimiento_in.equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    return crud_mantenimiento.crear_mantenimiento(
        db,
        equipo,
        tipo=mantenimiento_in.tipo,
        tecnico=mantenimiento_in.tecnico,
        descripcion=mantenimiento_in.descripcion,
        incidencia_ids=mantenimiento_in.incidencia_ids,
        costo_total=mantenimiento_in.costo_total,
    )
