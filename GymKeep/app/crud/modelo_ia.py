from sqlalchemy.orm import Session

from app.models.gymkeep import ModeloIA
from app.schemas.modelo_ia import ModeloIACreate


def list_modelos_ia(db: Session, skip: int = 0, limit: int = 100):
    return db.query(ModeloIA).order_by(ModeloIA.id).offset(skip).limit(limit).all()


def create_modelo_ia(db: Session, modelo_in: ModeloIACreate) -> ModeloIA:
    modelo = ModeloIA(**modelo_in.model_dump())
    db.add(modelo)
    db.commit()
    db.refresh(modelo)
    return modelo
