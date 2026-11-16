"""Periodos de los informes (mensual, trimestral, anual) y utilidades de fechas.

Es logica pura (sin base de datos) para poder probarla sola. Todo se mide en hora de Chile:
un reporte del 31 de octubre a las 23:30 pertenece a octubre aunque en UTC ya sea noviembre.
"""

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# En Windows sin el paquete tzdata no existe la base de zonas horarias: se usa un respaldo fijo.
try:
    ZONA_LOCAL = ZoneInfo("America/Santiago")
except ZoneInfoNotFoundError:  # pragma: no cover - depende del sistema
    ZONA_LOCAL = timezone(timedelta(hours=-3))

TIPOS_PERIODO = ("mensual", "trimestral", "anual")
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def hoy_local(ahora: datetime | None = None) -> date:
    ahora = ahora or datetime.now(timezone.utc)
    return ahora.astimezone(ZONA_LOCAL).date()


def nombre_mes(mes: int) -> str:
    return MESES[mes - 1].capitalize()


def meses_del_periodo(tipo: str, anio: int, mes: int | None = None, trimestre: int | None = None) -> list[tuple[int, int]]:
    """Lista de (anio, mes) que cubre el periodo: 1 mes, 3 meses o 12 meses."""
    if tipo not in TIPOS_PERIODO:
        raise ValueError("Periodo no valido: usa mensual, trimestral o anual.")
    if not 2000 <= anio <= 2100:
        raise ValueError("El año no es valido.")
    if tipo == "mensual":
        if mes is None or not 1 <= mes <= 12:
            raise ValueError("Indica el mes (1 a 12).")
        return [(anio, mes)]
    if tipo == "trimestral":
        if trimestre is None or not 1 <= trimestre <= 4:
            raise ValueError("Indica el trimestre (1 a 4).")
        primero = (trimestre - 1) * 3 + 1
        return [(anio, m) for m in range(primero, primero + 3)]
    return [(anio, m) for m in range(1, 13)]


def rango_mes(anio: int, mes: int) -> tuple[date, date]:
    """Primer y ultimo dia (inclusivo) del mes."""
    return date(anio, mes, 1), date(anio, mes, monthrange(anio, mes)[1])


def rango_periodo(tipo: str, anio: int, mes: int | None = None, trimestre: int | None = None) -> tuple[date, date]:
    meses = meses_del_periodo(tipo, anio, mes, trimestre)
    return rango_mes(*meses[0])[0], rango_mes(*meses[-1])[1]


def etiqueta_periodo(tipo: str, anio: int, mes: int | None = None, trimestre: int | None = None) -> str:
    if tipo == "mensual":
        return f"{nombre_mes(mes)} {anio}"
    if tipo == "trimestral":
        return f"Trimestre {trimestre} de {anio}"
    return f"Año {anio}"


def inicio_utc(dia: date) -> datetime:
    """Medianoche local del dia, como instante UTC (para filtrar en la base)."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=ZONA_LOCAL).astimezone(timezone.utc)


def fin_exclusivo_utc(dia: date) -> datetime:
    """Medianoche local del dia siguiente al `dia` dado, como UTC."""
    return inicio_utc(dia + timedelta(days=1))


def a_fecha_local(instante: datetime) -> date:
    """Fecha en Chile de un instante (si viene sin zona se asume UTC, como en SQLite)."""
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(ZONA_LOCAL).date()


def periodo_por_defecto(tipo: str, hoy: date) -> dict:
    """Ultimo periodo COMPLETO (el mes, trimestre o año anterior al actual)."""
    if tipo == "mensual":
        anterior = date(hoy.year, hoy.month, 1) - timedelta(days=1)
        return {"anio": anterior.year, "mes": anterior.month}
    if tipo == "trimestral":
        trimestre_actual = (hoy.month - 1) // 3 + 1
        if trimestre_actual == 1:
            return {"anio": hoy.year - 1, "trimestre": 4}
        return {"anio": hoy.year, "trimestre": trimestre_actual - 1}
    return {"anio": hoy.year - 1}
