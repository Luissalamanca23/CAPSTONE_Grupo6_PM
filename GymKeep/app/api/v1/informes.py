import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.informe import InformeExcelIn
from app.services import informe_periodos, informes, informes_excel

router = APIRouter()

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/borrador")
def borrador_de_informe(
    request: Request,
    tipo: str = Query("mensual", pattern="^(mensual|trimestral|anual)$"),
    anio: Optional[int] = Query(None, ge=2000, le=2100),
    mes: Optional[int] = Query(None, ge=1, le=12),
    trimestre: Optional[int] = Query(None, ge=1, le=4),
    sucursal_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Arma el informe de funcionamiento (una fila por maquina y por mes) para revisarlo y
    editarlo en pantalla. Sin `anio`/`mes`/`trimestre` toma el ultimo periodo completo.
    El responsable propuesto es quien tiene la sesion abierta."""
    hoy = informe_periodos.hoy_local()
    if anio is None:
        por_defecto = informe_periodos.periodo_por_defecto(tipo, hoy)
        anio = por_defecto["anio"]
        mes = mes or por_defecto.get("mes")
        trimestre = trimestre or por_defecto.get("trimestre")
    usuario = getattr(request.state, "usuario", None)
    try:
        return informes.construir_borrador(
            db,
            tipo=tipo,
            anio=anio,
            mes=mes,
            trimestre=trimestre,
            sucursal_id=sucursal_id,
            responsable=usuario.nombre if usuario else "",
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/excel")
def descargar_excel(informe: InformeExcelIn):
    """Convierte en Excel el informe tal como quedo editado en pantalla."""
    try:
        contenido = informes_excel.generar_excel(informe.model_dump())
    except ImportError:
        raise HTTPException(status_code=503, detail="Falta instalar openpyxl en el servidor (pip install openpyxl).")
    base = informe.nombre_archivo or f"informe_{informe.etiqueta or 'maquinas'}"
    nombre = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_") or "informe"
    return Response(
        content=contenido,
        media_type=TIPO_EXCEL,
        headers={"Content-Disposition": f'attachment; filename="{nombre}.xlsx"'},
    )
