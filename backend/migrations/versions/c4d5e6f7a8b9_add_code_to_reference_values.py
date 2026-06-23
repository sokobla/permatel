"""add code to reference_values

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-21 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reference_values', schema=None) as batch_op:
        batch_op.add_column(sa.Column('code', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('reference_values', schema=None) as batch_op:
        batch_op.drop_column('code')
