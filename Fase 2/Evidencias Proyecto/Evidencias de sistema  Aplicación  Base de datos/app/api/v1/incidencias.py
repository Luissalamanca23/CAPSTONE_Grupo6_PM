from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import equipamiento as crud_equipamiento
from app.crud import incidencia as crud_incidencia
from app.models.incidencia import ETIQUETA_TIPO_FALLA, EstadoIncidencia, TipoFalla
from app.schemas.incidencia import (
    IncidenciaCreate,
    IncidenciaCreateByQR,
    IncidenciaOut,
    IncidenciaUpdate,
    TipoFallaOut,
)

router = APIRouter()


@router.get("/tipos-falla", response_model=list[TipoFallaOut])
def listar_tipos_falla():
    """Catalogo de tipos de falla para las opciones de la encuesta del formulario publico."""
    return [{"valor": tipo, "etiqueta": ETIQUETA_TIPO_FALLA[tipo]} for tipo in TipoFalla]


@router.post("/", response_model=IncidenciaOut, status_code=status.HTTP_201_CREATED)
def crear_incidencia(incidencia_in: IncidenciaCreate, db: Session = Depends(get_db)):
    """Crea un reporte de incidencia indicando directamente el id interno del equipo
    (usado por el panel de tecnicos)."""
    equipo = crud_equipamiento.get_equipo(db, incidencia_in.equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo indicado no existe.")
    return crud_incidencia.create_incidencia(db, incidencia_in)


@router.post("/reporte-qr", response_model=IncidenciaOut, status_code=status.HTTP_201_CREATED)
def crear_incidencia_por_qr(incidencia_in: IncidenciaCreateByQR, db: Session = Depends(get_db)):
    """Portal de Reporte Express: el socio/personal escanea el QR de la maquina, elige el
    tipo de falla en la encuesta y escribe su nombre (unico campo de texto libre). La fecha
    y hora quedan registradas automaticamente y la prioridad se calcula sola."""
    equipo = crud_equipamiento.get_equipo_by_qr(db, incidencia_in.codigo_qr)
    if not equipo:
        raise HTTPException(status_code=404, detail="No existe un equipo con ese codigo QR.")
    incidencia_completa = IncidenciaCreate(
        equipo_id=equipo.id,
        tipo_falla=incidencia_in.tipo_falla,
        reportado_por=incidencia_in.reportado_por,
    )
    return crud_incidencia.create_incidencia(db, incidencia_completa)


@router.get("/", response_model=list[IncidenciaOut])
def listar_incidencias(
    skip: int = 0,
    limit: int = 100,
    estado: Optional[EstadoIncidencia] = None,
    equipo_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Lista incidencias, con filtros opcionales por estado y equipo (recientes primero)."""
    return crud_incidencia.list_incidencias(db, skip=skip, limit=limit, estado=estado, equipo_id=equipo_id)


@router.get("/{incidencia_id}", response_model=IncidenciaOut)
def obtener_incidencia(incidencia_id: int, db: Session = Depends(get_db)):
    incidencia = crud_incidencia.get_incidencia(db, incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada.")
    return incidencia


@router.patch("/{incidencia_id}", response_model=IncidenciaOut)
def actualizar_incidencia(incidencia_id: int, incidencia_in: IncidenciaUpdate, db: Session = Depends(get_db)):
    """Actualiza el estado/prioridad de una incidencia (usado por el panel de gestion de tecnicos)."""
    incidencia = crud_incidencia.get_incidencia(db, incidencia_id)
    if not incidencia:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada.")
    return crud_incidencia.update_incidencia(db, incidencia, incidencia_in)
