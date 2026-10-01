from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import equipamiento as crud_equipamiento
from app.crud import incidencia as crud_incidencia
from app.crud import tipo_falla as crud_tipo_falla
from app.models.gymkeep import EstadoIncidencia, PrioridadIncidencia
from app.schemas.incidencia import (
    IncidenciaCreate,
    IncidenciaCreateByQR,
    IncidenciaOut,
    IncidenciaUpdate,
    TipoFallaOut,
)

router = APIRouter()


@router.get("/tipos-falla", response_model=list[TipoFallaOut])
def listar_tipos_falla(solo_reporte_qr: bool = False, db: Session = Depends(get_db)):
    """Catalogo administrable de fallas (tabla `tipos_falla`). El formulario publico pide
    `solo_reporte_qr=true` para no mostrar fallas que solo puede detectar la IA
    (ej. MOVIMIENTO_ANOMALO); el panel de tecnicos ve el catalogo completo."""
    return crud_tipo_falla.list_tipos_falla(db, solo_reporte_qr=solo_reporte_qr)


@router.post("/", response_model=IncidenciaOut, status_code=status.HTTP_201_CREATED)
def crear_incidencia(incidencia_in: IncidenciaCreate, db: Session = Depends(get_db)):
    """Crea un reporte de incidencia indicando directamente el id interno del equipo
    (usado por el panel de tecnicos)."""
    equipo = crud_equipamiento.get_equipo(db, incidencia_in.equipo_id)
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo indicado no existe.")

    tipo_falla = crud_tipo_falla.get_tipo_falla_by_codigo(db, incidencia_in.tipo_falla_codigo)
    if not tipo_falla:
        raise HTTPException(status_code=404, detail="El tipo de falla indicado no existe en el catalogo.")

    return crud_incidencia.create_incidencia(db, incidencia_in, tipo_falla)


@router.post("/reporte-qr", response_model=IncidenciaOut, status_code=status.HTTP_201_CREATED)
def crear_incidencia_por_qr(incidencia_in: IncidenciaCreateByQR, db: Session = Depends(get_db)):
    """Portal de Reporte Express: el socio/personal escanea el QR de la maquina, elige el
    tipo de falla en la encuesta y escribe su nombre (unico campo de texto libre). La fecha
    y hora quedan registradas automaticamente y la prioridad se calcula sola segun la
    prioridad_base del tipo de falla."""
    equipo = crud_equipamiento.get_equipo_by_token(db, incidencia_in.token)
    if not equipo:
        raise HTTPException(status_code=404, detail="El codigo QR no es valido o ya no esta activo.")

    tipo_falla = crud_tipo_falla.get_tipo_falla_by_codigo(db, incidencia_in.tipo_falla_codigo)
    if not tipo_falla or not tipo_falla.permite_reporte_qr:
        raise HTTPException(
            status_code=400, detail="Ese tipo de falla no esta disponible en el formulario publico."
        )

    return crud_incidencia.create_incidencia_por_qr(
        db,
        equipo,
        tipo_falla,
        incidencia_in.reportado_por,
        gravedad=incidencia_in.gravedad,
        funcional=incidencia_in.funcional,
        descripcion=incidencia_in.descripcion,
    )


@router.get("/", response_model=list[IncidenciaOut])
def listar_incidencias(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    estado: Optional[EstadoIncidencia] = None,
    equipo_id: Optional[int] = None,
    categoria: Optional[str] = None,
    prioridad: Optional[PrioridadIncidencia] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Lista incidencias del historial (panel de tecnicos), mas recientes primero.

    Filtros opcionales, todos combinables: estado, equipo, categoria del tipo de falla
    (mecanica/electrica/otro), prioridad, rango de fechas (fecha_desde/fecha_hasta, por
    dia) y `q` (texto libre: busca en descripcion, quien reporto, tipo de falla y nombre
    del equipo). El total que cumple los filtros (ignorando skip/limit) va en el header
    `X-Total-Count`, para que el panel arme la paginacion sin traer todo de una vez."""
    filtros = dict(
        estado=estado,
        equipo_id=equipo_id,
        categoria=categoria,
        prioridad=prioridad,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        q=q,
    )
    response.headers["X-Total-Count"] = str(crud_incidencia.count_incidencias(db, **filtros))
    return crud_incidencia.list_incidencias(db, skip=skip, limit=limit, **filtros)


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
