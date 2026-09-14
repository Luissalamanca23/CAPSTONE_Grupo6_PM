"""GymKeep esquema ampliado

Revision ID: 0001_gymkeep_ampliado
Revises:
Create Date: 2026-09-10

IMPORTANTE:
Esta migración asume una base nueva o una migración controlada desde el modelo
anterior. Para bases con datos reales, crear una migración de transformación
específica en lugar de ejecutar DROP/RESET.
"""

from alembic import op

revision = "0001_gymkeep_ampliado"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # El esquema SQL completo y los triggers están versionados en postgres/schema.sql.
    # Para el Capstone, este archivo permite aplicar la estructura desde Alembic
    # manteniendo un único artefacto SQL auditable.
    with open("postgres/schema.sql", "r", encoding="utf-8") as f:
        op.execute(f.read())


def downgrade():
    # Downgrade conservador: no elimina datos automáticamente.
    # En un entorno académico/development puede reemplazarse por DROP TABLE,
    # pero se evita aquí para prevenir pérdida accidental.
    pass
