from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import Camara, Equipo
from app.schemas.camara import CamaraCreate


def get_camara(db: Session, camara_id: int) -> Optional[Camara]:
    return db.query(Camara).filter(Camara.id == camara_id).first()


def list_camaras(db: Session, sucursal_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(Camara)
    if sucursal_id is not None:
        query = query.filter(Camara.sucursal_id == sucursal_id)
    return query.order_by(Camara.id).offset(skip).limit(limit).all()


def create_camara(db: Session, camara_in: CamaraCreate) -> Camara:
    datos = camara_in.model_dump(exclude={"equipo_ids"})
    camara = Camara(**datos)
    if camara_in.equipo_ids:
        camara.equipos = db.query(Equipo).filter(Equipo.id.in_(camara_in.equipo_ids)).all()
    db.add(camara)
    db.commit()
    db.refresh(camara)
    return camara
