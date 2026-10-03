from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import sesion_uso as crud_sesion_uso
from app.schemas.sesion_uso import HorometroEquipoOut, SesionUsoOut

router = APIRouter()


@router.get("/", response_model=list[SesionUsoOut])
def listar_sesiones_uso(
    equipo_id: Optional[int] = None,
    estado: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Sesiones de uso de los equipos (mas recientes primero). Las genera el modulo de
    vision al enviar sus eventos inicio_uso / fin_uso a POST /eventos-ia/."""
    return crud_sesion_uso.list_sesiones_uso(db, equipo_id=equipo_id, estado=estado, skip=skip, limit=limit)


@router.get("/horometro", response_model=list[HorometroEquipoOut])
def horometro(equipo_id: Optional[int] = None, desde: Optional[datetime] = None, db: Session = Depends(get_db)):
    """Horas de uso acumuladas por equipo (horometro virtual): base del mantenimiento
    preventivo por uso. Cuenta la union de los intervalos de las sesiones cerradas, asi
    que dos sesiones solapadas no suman doble."""
    return crud_sesion_uso.horometro(db, equipo_id=equipo_id, desde=desde)
