"""prises de service (vacations agents)

Revision ID: b1c2d3e4f5a6
Revises: f3a4b5c6d7e8
Create Date: 2026-06-24 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'b1c2d3e4f5a6'
down_revision = 'f3a4b5c6d7e8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prises_de_service',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=True),
        sa.Column('date_debut', sa.DateTime(), nullable=False),
        sa.Column('date_fin', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents_securite.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prises_de_service_tenant_id', 'prises_de_service', ['tenant_id'])
    op.create_index('ix_prises_de_service_agent_id', 'prises_de_service', ['agent_id'])
    op.create_index('ix_prises_de_service_client_id', 'prises_de_service', ['client_id'])
    op.create_index('ix_prises_de_service_site_id', 'prises_de_service', ['site_id'])
    op.create_index('ix_pds_tenant_agent_open', 'prises_de_service', ['tenant_id', 'agent_id', 'date_fin'])


def downgrade():
    op.drop_index('ix_pds_tenant_agent_open', table_name='prises_de_service')
    op.drop_index('ix_prises_de_service_site_id', table_name='prises_de_service')
    op.drop_index('ix_prises_de_service_client_id', table_name='prises_de_service')
    op.drop_index('ix_prises_de_service_agent_id', table_name='prises_de_service')
    op.drop_index('ix_prises_de_service_tenant_id', table_name='prises_de_service')
    op.drop_table('prises_de_service')
