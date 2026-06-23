"""add contact_id to interactions

Revision ID: d1a2b3c4e5f6
Revises: b8565ce8f5a1
Create Date: 2026-06-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1a2b3c4e5f6'
down_revision = 'b8565ce8f5a1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('interactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_interactions_contact_id'), ['contact_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_interactions_contact_id', 'contacts', ['contact_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('interactions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_interactions_contact_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_interactions_contact_id'))
        batch_op.drop_column('contact_id')
