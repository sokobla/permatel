"""reference_values.is_discriminant (classification anomalies discriminantes)

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-22 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd1e2f3a4b5c6'
down_revision = 'c0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reference_values', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_discriminant', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Pas de backfill : chaque tenant choisit explicitement ses natures discriminantes.


def downgrade():
    with op.batch_alter_table('reference_values', schema=None) as batch_op:
        batch_op.drop_column('is_discriminant')
