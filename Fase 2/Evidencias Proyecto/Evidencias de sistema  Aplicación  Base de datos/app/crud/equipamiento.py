from typing import Optional

from sqlalchemy.orm import Session

from app.models.equipamiento import Equipo
from app.schemas.equipamiento import EquipoCreate, EquipoUpdate


def get_equipo(db: Session, equipo_id: int) -> Optional[Equipo]:
    return db.query(Equipo).filter(Equipo.id == equipo_id).first()


def get_equipo_by_qr(db: Session, codigo_qr: str) -> Optional[Equipo]:
    return db.query(Equipo).filter(Equipo.codigo_qr == codigo_qr).first()


def list_equipos(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Equipo).offset(skip).limit(limit).all()


def create_equipo(db: Session, equipo_in: EquipoCreate) -> Equipo:
    equipo = Equipo(**equipo_in.model_dump())
    db.add(equipo)
    db.commit()
    db.refresh(equipo)
    return equipo


def update_equipo(db: Session, equipo: Equipo, equipo_in: EquipoUpdate) -> Equipo:
    for campo, valor in equipo_in.model_dump(exclude_unset=True).items():
        setattr(equipo, campo, valor)
    db.commit()
    db.refresh(equipo)
    return equipo


def delete_equipo(db: Session, equipo: Equipo) -> None:
    db.delete(equipo)
    db.commit()
