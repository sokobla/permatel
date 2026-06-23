"""add created_by_id and updated_by_id to demandes

Revision ID: a7f3e9c12b45
Revises: 5ba83a29c9ce
Create Date: 2026-06-18

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7f3e9c12b45'
down_revision = '5ba83a29c9ce'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('demandes', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.add_column('demandes', sa.Column('updated_by_id', sa.Integer(), nullable=True))

    op.create_index('ix_demandes_created_by_id', 'demandes', ['created_by_id'])
    op.create_index('ix_demandes_updated_by_id', 'demandes', ['updated_by_id'])

    op.create_foreign_key(
        'fk_demandes_created_by',
        'demandes', 'users',
        ['created_by_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_demandes_updated_by',
        'demandes', 'users',
        ['updated_by_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_demandes_updated_by', 'demandes', type_='foreignkey')
    op.drop_constraint('fk_demandes_created_by', 'demandes', type_='foreignkey')
    op.drop_index('ix_demandes_updated_by_id', table_name='demandes')
    op.drop_index('ix_demandes_created_by_id', table_name='demandes')
    op.drop_column('demandes', 'updated_by_id')
    op.drop_column('demandes', 'created_by_id')
