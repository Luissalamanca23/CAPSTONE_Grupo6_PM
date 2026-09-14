from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import modelo_ia as crud_modelo_ia
from app.schemas.modelo_ia import ModeloIACreate, ModeloIAOut

router = APIRouter()


@router.get("/", response_model=list[ModeloIAOut])
def listar_modelos_ia(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Versiones de modelos de IA registradas (para trazabilidad de que modelo genero
    cada evento/incidencia por IA)."""
    return crud_modelo_ia.list_modelos_ia(db, skip=skip, limit=limit)


@router.post("/", response_model=ModeloIAOut, status_code=status.HTTP_201_CREATED)
def crear_modelo_ia(modelo_in: ModeloIACreate, db: Session = Depends(get_db)):
    return crud_modelo_ia.create_modelo_ia(db, modelo_in)
