"""merge final heads: created_by/updated_by + contact_id branches

Revision ID: f1a2b3c4d5e6
Revises: a7f3e9c12b45, e9f0a1b2c3d4
Create Date: 2026-06-19 21:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = ('a7f3e9c12b45', 'e9f0a1b2c3d4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
