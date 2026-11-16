"""Informe de funcionamiento de las maquinas: una fila por maquina y por mes del periodo.

`construir_borrador` arma el informe a partir de la base; el usuario lo revisa y edita en
pantalla y despues se baja como Excel (services/informes_excel.py).
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.gymkeep import (
    Empresa,
    Equipo,
    EstadoEquipo,
    Incidencia,
    Mantenimiento,
    SesionUso,
    Sucursal,
)
from app.services import informe_filas as filas
from app.services import informe_periodos as periodos


def datos_del_gimnasio(db: Session, sucursal_id: Optional[int] = None) -> tuple[Optional[Sucursal], str]:
    """Sucursal elegida (o la primera) y el nombre que sale en el encabezado del informe."""
    consulta = db.query(Sucursal).order_by(Sucursal.id)
    sucursal = db.get(Sucursal, sucursal_id) if sucursal_id else consulta.first()
    if sucursal is None:
        return None, "Gimnasio"
    empresa = db.get(Empresa, sucursal.empresa_id)
    nombre = sucursal.nombre
    if empresa and (empresa.nombre_fantasia or empresa.razon_social) and (empresa.nombre_fantasia or empresa.razon_social) not in nombre:
        nombre = f"{nombre} ({empresa.nombre_fantasia or empresa.razon_social})"
    return sucursal, nombre


def construir_borrador(
    db: Session,
    *,
    tipo: str,
    anio: int,
    mes: Optional[int] = None,
    trimestre: Optional[int] = None,
    sucursal_id: Optional[int] = None,
    responsable: str = "",
    ahora: Optional[datetime] = None,
) -> dict:
    meses = periodos.meses_del_periodo(tipo, anio, mes, trimestre)  # valida los parametros
    desde, hasta = periodos.rango_periodo(tipo, anio, mes, trimestre)
    ahora = ahora or datetime.now(timezone.utc)
    hoy = periodos.hoy_local(ahora)
    sucursal, nombre_gimnasio = datos_del_gimnasio(db, sucursal_id)

    consulta_equipos = db.query(Equipo).filter(Equipo.estado != EstadoEquipo.retirado)
    if sucursal is not None:
        consulta_equipos = consulta_equipos.filter(Equipo.sucursal_id == sucursal.id)
    equipos = consulta_equipos.order_by(Equipo.codigo_activo).all()
    ids = [e.id for e in equipos]

    inicio = periodos.inicio_utc(desde)
    fin = periodos.fin_exclusivo_utc(hasta)

    incidencias: dict[int, list[dict]] = defaultdict(list)
    mantenimientos: dict[int, list[dict]] = defaultdict(list)
    uso: dict[tuple[int, int, int], list[float]] = defaultdict(lambda: [0.0, set()])

    if ids:
        # Incidencias reportadas hasta el fin del periodo que no se cerraron antes de que empiece
        # (las abiertas de meses anteriores cuentan para el estado de cada mes).
        for inc in (
            db.query(Incidencia)
            .filter(Incidencia.equipo_id.in_(ids), Incidencia.fecha_reporte < fin)
            .filter((Incidencia.fecha_resolucion.is_(None)) | (Incidencia.fecha_resolucion >= inicio))
            .all()
        ):
            incidencias[inc.equipo_id].append(
                {
                    "fecha": periodos.a_fecha_local(inc.fecha_reporte),
                    "tipo": inc.tipo_falla.nombre if inc.tipo_falla else "Falla",
                    "prioridad": inc.prioridad.value,
                    "estado": inc.estado.value,
                    "fecha_cierre": periodos.a_fecha_local(inc.fecha_resolucion) if inc.fecha_resolucion else None,
                }
            )
        for m in (
            db.query(Mantenimiento)
            .filter(Mantenimiento.equipo_id.in_(ids), Mantenimiento.fecha_inicio >= inicio, Mantenimiento.fecha_inicio < fin)
            .all()
        ):
            mantenimientos[m.equipo_id].append(
                {
                    "fecha": periodos.a_fecha_local(m.fecha_inicio),
                    "tipo": m.tipo,
                    "fin": periodos.a_fecha_local(m.fecha_fin) if m.fecha_fin else None,
                }
            )
        for equipo_id, fecha_inicio, segundos in (
            db.query(SesionUso.equipo_id, SesionUso.fecha_inicio, SesionUso.duracion_segundos)
            .filter(SesionUso.equipo_id.in_(ids), SesionUso.fecha_inicio >= inicio, SesionUso.fecha_inicio < fin)
            .all()
        ):
            dia = periodos.a_fecha_local(fecha_inicio)
            celda = uso[(equipo_id, dia.year, dia.month)]
            celda[0] += (segundos or 0) / 3600.0
            celda[1].add(dia)

    salida = []
    for anio_m, mes_m in meses:
        primero, ultimo = periodos.rango_mes(anio_m, mes_m)
        en_curso = primero <= hoy <= ultimo
        if primero > hoy:
            continue  # un mes que aun no llega no tiene nada que informar
        for e in equipos:
            instalada = e.fecha_instalacion or e.fecha_adquisicion
            if instalada and instalada > ultimo:
                continue  # todavia no existia en ese mes
            propias = incidencias.get(e.id, [])
            del_mes = filas.incidencias_del_mes(propias, primero, ultimo)
            abiertas = filas.abiertas_al_cierre(propias, ultimo)
            mant_mes = [m for m in mantenimientos.get(e.id, []) if primero <= m["fecha"] <= ultimo]
            en_mant = any(m["fin"] is None or m["fin"] > ultimo for m in mant_mes)
            horas, dias = uso.get((e.id, anio_m, mes_m), [0.0, set()])
            salida.append(
                {
                    "fecha": f"{periodos.nombre_mes(mes_m)} {anio_m}",
                    "equipo_id": e.id,
                    "codigo": e.codigo_activo,
                    "maquina": e.nombre,
                    "incidencias": filas.texto_incidencias(del_mes),
                    "mantenimientos": filas.texto_mantenimientos(mant_mes),
                    "observaciones": filas.texto_observaciones(
                        horas_uso=horas,
                        dias_con_uso=len(dias),
                        del_mes_incidencias=len(del_mes),
                        observacion_equipo=e.observaciones,
                    ),
                    "estado": filas.estado_del_mes(
                        estado_actual=e.estado.value,
                        es_mes_en_curso=en_curso,
                        abiertas_cierre=abiertas,
                        en_mantenimiento_al_cierre=en_mant,
                    ),
                }
            )

    return {
        "gimnasio": nombre_gimnasio,
        "responsable": responsable,
        "tipo": tipo,
        "etiqueta": periodos.etiqueta_periodo(tipo, anio, mes, trimestre),
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "generado": hoy.isoformat(),
        "filas": salida,
    }
