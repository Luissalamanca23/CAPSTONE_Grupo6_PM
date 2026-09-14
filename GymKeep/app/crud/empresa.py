from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import Empresa
from app.schemas.empresa import EmpresaCreate


def get_empresa(db: Session, empresa_id: int) -> Optional[Empresa]:
    return db.query(Empresa).filter(Empresa.id == empresa_id).first()


def list_empresas(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Empresa).order_by(Empresa.id).offset(skip).limit(limit).all()


def create_empresa(db: Session, empresa_in: EmpresaCreate) -> Empresa:
    empresa = Empresa(**empresa_in.model_dump())
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa
