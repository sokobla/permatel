"""merge heads: add_contact_id_to_interactions + add_agent_concerne_to_demandes

Revision ID: e9f0a1b2c3d4
Revises: d1a2b3c4e5f6, f25dc29abb83
Create Date: 2026-06-19 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9f0a1b2c3d4'
down_revision = ('d1a2b3c4e5f6', 'f25dc29abb83')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
