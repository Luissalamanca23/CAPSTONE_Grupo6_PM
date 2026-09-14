from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import Zona
from app.schemas.zona import ZonaCreate


def get_zona(db: Session, zona_id: int) -> Optional[Zona]:
    return db.query(Zona).filter(Zona.id == zona_id).first()


def list_zonas(db: Session, sucursal_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Zona)
    if sucursal_id is not None:
        query = query.filter(Zona.sucursal_id == sucursal_id)
    return query.order_by(Zona.id).offset(skip).limit(limit).all()


def create_zona(db: Session, zona_in: ZonaCreate) -> Zona:
    zona = Zona(**zona_in.model_dump())
    db.add(zona)
    db.commit()
    db.refresh(zona)
    return zona
