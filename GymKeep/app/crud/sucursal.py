from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import Sucursal
from app.schemas.sucursal import SucursalCreate


def get_sucursal(db: Session, sucursal_id: int) -> Optional[Sucursal]:
    return db.query(Sucursal).filter(Sucursal.id == sucursal_id).first()


def list_sucursales(db: Session, empresa_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Sucursal)
    if empresa_id is not None:
        query = query.filter(Sucursal.empresa_id == empresa_id)
    return query.order_by(Sucursal.id).offset(skip).limit(limit).all()


def create_sucursal(db: Session, sucursal_in: SucursalCreate) -> Sucursal:
    sucursal = Sucursal(**sucursal_in.model_dump())
    db.add(sucursal)
    db.commit()
    db.refresh(sucursal)
    return sucursal
