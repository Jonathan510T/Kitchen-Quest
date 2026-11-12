"""add challenge servings and resync id sequence

Adds challenges.servings (editing challenges needs it)

Revision ID: b7d2e4f19a60
Revises: a3f1c9d27b44
Create Date: 2026-11-12 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d2e4f19a60'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d27b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c['name'] for c in sa.inspect(bind).get_columns('challenges')}

    if 'servings' not in columns:
        with op.batch_alter_table('challenges') as batch:
            batch.add_column(
                sa.Column('servings', sa.Integer(), nullable=False, server_default='1')
            )
        op.execute(
            "UPDATE challenges SET servings = 2 "
            "WHERE title IN ('QA Tomato Soup', 'Rustic Pasta Pomodoro')"
        )

    if bind.dialect.name == 'postgresql':
        op.execute(
            "SELECT setval(pg_get_serial_sequence('challenges', 'id'), "
            "COALESCE((SELECT MAX(id) FROM challenges), 0) + 1, false)"
        )


def downgrade() -> None:
    with op.batch_alter_table('challenges') as batch:
        batch.drop_column('servings')