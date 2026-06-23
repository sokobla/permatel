"""add logo_url to tenants

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('logo_url', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('logo_url')
