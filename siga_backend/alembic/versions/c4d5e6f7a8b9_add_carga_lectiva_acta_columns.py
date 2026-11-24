"""add_carga_lectiva_acta_columns

Añade las columnas de control de actas y fecha límite de notas a la tabla
``carga_lectiva``. El modelo ORM ya las declaraba, pero la tabla física no las
tenía, lo que provocaba errores 500 en los endpoints de carga lectiva del
docente (sílabos y plan de trabajo).

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-11-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columnas_existentes(tabla: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(tabla):
        return set()
    return {col["name"] for col in inspector.get_columns(tabla)}


def upgrade() -> None:
    existentes = _columnas_existentes("carga_lectiva")
    if not existentes:
        # La tabla se crea en el volcado inicial; si no existe, no hay nada que migrar.
        return

    if "fecha_limite_notas" not in existentes:
        op.add_column("carga_lectiva", sa.Column("fecha_limite_notas", sa.Date(), nullable=True))
    if "acta_cerrada" not in existentes:
        op.add_column(
            "carga_lectiva",
            sa.Column("acta_cerrada", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "acta_cerrada_at" not in existentes:
        op.add_column("carga_lectiva", sa.Column("acta_cerrada_at", sa.TIMESTAMP(), nullable=True))
    if "acta_cerrada_por" not in existentes:
        op.add_column("carga_lectiva", sa.Column("acta_cerrada_por", sa.Integer(), nullable=True))


def downgrade() -> None:
    existentes = _columnas_existentes("carga_lectiva")
    for columna in ("acta_cerrada_por", "acta_cerrada_at", "acta_cerrada", "fecha_limite_notas"):
        if columna in existentes:
            op.drop_column("carga_lectiva", columna)
