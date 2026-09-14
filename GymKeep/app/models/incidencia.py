"""OBSOLETO: el modelo de incidencias (y el catalogo de tipos de falla) se movio a
app/models/gymkeep.py como parte de la integracion con el esquema ampliado. El antiguo
enum fijo `TipoFalla` ahora es la tabla catalogo `tipos_falla` (ver
GymKeep_BDD_Completa/INTEGRACION_REPO_ACTUAL.md).

Este archivo se mantiene solo como referencia historica y no se importa desde ningun otro
modulo (ver app/models/__init__.py). No define clases para evitar registrar tablas
duplicadas en Base.metadata.
"""
