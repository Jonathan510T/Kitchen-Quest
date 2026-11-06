"""add gameplay and progression tables

Creates challenges, attempts, user_progress and challenge_progress.

The first three were previously created by Base.metadata.create_all() in
main.py and never had a migration, so a developer database may already contain
them. Each table is therefore only created when it is missing, and
attempts.created_at is only converted when it is still a string column.
challenge_progress is backfilled from existing attempts.

Revision ID: a3f1c9d27b44
Revises: 58ee3321c7ba
Create Date: 2026-11-04 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d27b44'
down_revision: Union[str, Sequence[str], None] = '58ee3321c7ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _convert_created_at_portable(bind) -> None:
    """String -> DateTime for non-PostgreSQL databases (e.g. the SQLite fallback).

    A batch ALTER on SQLite rebuilds the table with CAST(created_at AS DATETIME),
    which turns '2026-10-21T10:00:00+00:00' into the integer 2026 and destroys the
    data. Parse the text in Python into a new column instead, then swap it in.
    """
    from datetime import datetime, timezone

    with op.batch_alter_table('attempts') as batch:
        batch.add_column(sa.Column('created_at_dt', sa.DateTime(timezone=True), nullable=True))

    attempts = sa.table(
        'attempts',
        sa.column('id', sa.Integer),
        sa.column('created_at', sa.String),
        sa.column('created_at_dt', sa.DateTime(timezone=True)),
    )
    for row_id, text in bind.execute(sa.select(attempts.c.id, attempts.c.created_at)).all():
        try:
            parsed = datetime.fromisoformat(text)
        except (TypeError, ValueError):
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        bind.execute(
            attempts.update().where(attempts.c.id == row_id).values(created_at_dt=parsed)
        )

    with op.batch_alter_table('attempts') as batch:
        batch.drop_column('created_at')
    with op.batch_alter_table('attempts') as batch:
        batch.alter_column(
            'created_at_dt',
            new_column_name='created_at',
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
            nullable=False,
        )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if 'challenges' not in tables:
        op.create_table('challenges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipe_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('difficulty', sa.String(length=30), nullable=False),
        sa.Column('base_xp', sa.Integer(), nullable=False),
        sa.Column('time_limit_seconds', sa.Integer(), nullable=False),
        sa.Column('chef_tip', sa.Text(), nullable=True),
        sa.Column('steps_json', sa.Text(), nullable=False),
        sa.Column('ingredients_json', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_challenges_title'), 'challenges', ['title'], unique=False)

    if 'attempts' not in tables:
        op.create_table('attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.Integer(), nullable=False),
        sa.Column('accuracy_score', sa.Float(), nullable=False),
        sa.Column('stars', sa.Integer(), nullable=False),
        sa.Column('xp_earned', sa.Integer(), nullable=False),
        sa.Column('time_taken_seconds', sa.Float(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('feedback_json', sa.Text(), nullable=True),
        sa.Column('actions_log_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_attempts_challenge_id'), 'attempts', ['challenge_id'], unique=False)
        op.create_index(op.f('ix_attempts_created_at'), 'attempts', ['created_at'], unique=False)
        op.create_index(op.f('ix_attempts_user_id'), 'attempts', ['user_id'], unique=False)
    else:
        # Existing table from create_all(): created_at was a String(50) holding ISO-8601 text.
        created_col = next(c for c in insp.get_columns('attempts') if c['name'] == 'created_at')
        if isinstance(created_col['type'], sa.String):
            if bind.dialect.name == 'postgresql':
                op.alter_column(
                    'attempts',
                    'created_at',
                    existing_type=sa.String(length=50),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False,
                    postgresql_using='created_at::timestamptz',
                )
            else:
                _convert_created_at_portable(bind)
        existing_indexes = {i['name'] for i in insp.get_indexes('attempts')}
        if 'ix_attempts_created_at' not in existing_indexes:
            op.create_index(op.f('ix_attempts_created_at'), 'attempts', ['created_at'], unique=False)

    if 'user_progress' not in tables:
        op.create_table('user_progress',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_xp', sa.Integer(), nullable=False),
        sa.Column('current_level', sa.Integer(), nullable=False),
        sa.Column('rank_title', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
        )

    if 'challenge_progress' not in tables:
        op.create_table('challenge_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.Integer(), nullable=False),
        sa.Column('best_stars', sa.Integer(), nullable=False),
        sa.Column('best_score', sa.Float(), nullable=False),
        sa.Column('best_time_seconds', sa.Float(), nullable=True),
        sa.Column('attempts_count', sa.Integer(), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column('first_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'challenge_id')
        )
        op.create_index(op.f('ix_challenge_progress_challenge_id'), 'challenge_progress', ['challenge_id'], unique=False)
        op.create_index(op.f('ix_challenge_progress_user_id'), 'challenge_progress', ['user_id'], unique=False)

    # Backfill per-challenge results from any attempts that already exist.
    op.execute(
        """
        INSERT INTO challenge_progress (
            user_id, challenge_id, best_stars, best_score, best_time_seconds,
            attempts_count, completed, first_completed_at, last_attempt_at
        )
        SELECT
            a.user_id,
            a.challenge_id,
            MAX(a.stars),
            MAX(a.accuracy_score),
            MIN(CASE WHEN a.passed THEN a.time_taken_seconds END),
            COUNT(*),
            SUM(CASE WHEN a.passed THEN 1 ELSE 0 END) > 0,
            MIN(CASE WHEN a.passed THEN a.created_at END),
            MAX(a.created_at)
        FROM attempts a
        WHERE NOT EXISTS (
            SELECT 1 FROM challenge_progress cp
            WHERE cp.user_id = a.user_id AND cp.challenge_id = a.challenge_id
        )
        GROUP BY a.user_id, a.challenge_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_challenge_progress_user_id'), table_name='challenge_progress')
    op.drop_index(op.f('ix_challenge_progress_challenge_id'), table_name='challenge_progress')
    op.drop_table('challenge_progress')
    # user_progress, attempts and challenges are left in place: they pre-date
    # this migration on databases built with create_all(), so dropping them
    # here would destroy data this revision did not create.