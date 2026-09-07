"""Importa todos los modelos para que queden registrados en Base.metadata."""
from app.models.equipamiento import Equipo, EstadoEquipo  # noqa: F401
from app.models.incidencia import Incidencia, EstadoIncidencia, PrioridadIncidencia  # noqa: F401
