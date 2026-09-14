from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import empresa as crud_empresa
from app.schemas.empresa import EmpresaCreate, EmpresaOut

router = APIRouter()


@router.get("/", response_model=list[EmpresaOut])
def listar_empresas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lista las empresas (clientes/organizaciones) registradas. Para el Capstone suele
    existir una sola, creada por la data de ejemplo (seed.sql)."""
    return crud_empresa.list_empresas(db, skip=skip, limit=limit)


@router.post("/", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def crear_empresa(empresa_in: EmpresaCreate, db: Session = Depends(get_db)):
    return crud_empresa.create_empresa(db, empresa_in)
