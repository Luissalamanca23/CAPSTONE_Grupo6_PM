"""Texto y estado de cada fila del informe (una fila por maquina y por mes).

Logica pura: recibe datos simples (diccionarios) y devuelve texto. La consulta a la base
esta en services/informes.py.
"""

from datetime import date, datetime

ESTADO_ETIQUETA = {
    "operativo": "Operativo",
    "en_mantenimiento": "En mantenimiento",
    "fuera_de_servicio": "Fuera de servicio",
    "retirado": "Retirado",
    "con_incidencias": "Operativo con incidencias abiertas",
}
PRIORIDAD_ETIQUETA = {"baja": "baja", "media": "media", "alta": "alta", "urgente": "urgente"}
TIPO_MANT_ETIQUETA = {"preventivo": "preventivo", "correctivo": "correctivo", "inspeccion": "inspección"}
ESTADOS_ABIERTOS = ("pendiente", "en_proceso")
ESTADO_INCIDENCIA_ETIQUETA = {
    "pendiente": "pendiente", "en_proceso": "en proceso", "resuelta": "resuelta", "descartada": "descartada",
}


def _dia(valor) -> date:
    return valor.date() if isinstance(valor, datetime) else valor


def incidencias_del_mes(incidencias: list[dict], inicio: date, fin: date) -> list[dict]:
    """Incidencias reportadas dentro del mes (por fecha local de reporte)."""
    return sorted((i for i in incidencias if inicio <= i["fecha"] <= fin), key=lambda i: i["fecha"])


def abiertas_al_cierre(incidencias: list[dict], fin: date) -> list[dict]:
    """Incidencias ya reportadas al cierre del mes y aun sin resolver ese dia."""
    abiertas = []
    for i in incidencias:
        if i["fecha"] > fin:
            continue
        if i["fecha_cierre"] is not None:
            if i["fecha_cierre"] > fin:
                abiertas.append(i)
        elif i["estado"] in ESTADOS_ABIERTOS:
            abiertas.append(i)
    return abiertas


def texto_incidencias(del_mes: list[dict]) -> str:
    if not del_mes:
        return "Sin incidencias"
    partes = []
    for i in del_mes:
        estado = ESTADO_INCIDENCIA_ETIQUETA.get(i["estado"], i["estado"])
        partes.append(f"{i['fecha'].strftime('%d-%m')} {i['tipo']} (prioridad {PRIORIDAD_ETIQUETA.get(i['prioridad'], i['prioridad'])}, {estado})")
    n = len(del_mes)
    return f"{n} incidencia{'s' if n != 1 else ''}: " + "; ".join(partes)


def texto_mantenimientos(del_mes: list[dict]) -> str:
    if not del_mes:
        return "Sin mantenimientos"
    por_tipo: dict[str, list[date]] = {}
    for m in sorted(del_mes, key=lambda m: m["fecha"]):
        por_tipo.setdefault(m["tipo"], []).append(m["fecha"])
    partes = []
    for tipo, fechas in por_tipo.items():
        nombre = TIPO_MANT_ETIQUETA.get(tipo, tipo)
        dias = ", ".join(f.strftime("%d-%m") for f in fechas)
        partes.append(f"{len(fechas)} {nombre} ({dias})")
    return "; ".join(partes)


def estado_del_mes(
    *,
    estado_actual: str,
    es_mes_en_curso: bool,
    abiertas_cierre: list[dict],
    en_mantenimiento_al_cierre: bool = False,
) -> str:
    """Estado de la maquina para ese mes. El mes en curso usa el estado real de hoy; los meses
    pasados se deducen de las incidencias que seguian abiertas al cerrar el mes."""
    if estado_actual == "retirado":
        return ESTADO_ETIQUETA["retirado"]
    if es_mes_en_curso:
        return ESTADO_ETIQUETA.get(estado_actual, estado_actual)
    if any(i["prioridad"] == "urgente" for i in abiertas_cierre):
        return ESTADO_ETIQUETA["fuera_de_servicio"]
    if en_mantenimiento_al_cierre:
        return ESTADO_ETIQUETA["en_mantenimiento"]
    if abiertas_cierre:
        return ESTADO_ETIQUETA["con_incidencias"]
    return ESTADO_ETIQUETA["operativo"]


def texto_observaciones(*, horas_uso: float, dias_con_uso: int, del_mes_incidencias: int, observacion_equipo: str | None,
                        aun_no_instalada: bool = False) -> str:
    if aun_no_instalada:
        return "Aún no instalada en este mes."
    partes = []
    if horas_uso > 0:
        partes.append(f"Uso registrado: {horas_uso:.0f} h en {dias_con_uso} día{'s' if dias_con_uso != 1 else ''}.")
    else:
        partes.append("Sin uso registrado.")
    if del_mes_incidencias == 0:
        partes.append("Sin fallas en el mes.")
    if observacion_equipo:
        partes.append(observacion_equipo.strip())
    return " ".join(partes)
