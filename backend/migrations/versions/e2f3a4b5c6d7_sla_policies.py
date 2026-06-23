"""sla_policies + colonnes SLA sur demandes

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-23 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sla_policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('priorite', sa.String(length=20), nullable=False),
        sa.Column('type_demande', sa.String(length=20), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('response_minutes', sa.Integer(), nullable=False),
        sa.Column('resolution_minutes', sa.Integer(), nullable=False),
        sa.Column('warning_pct', sa.Integer(), nullable=False, server_default='80'),
        sa.Column('pause_on_waiting', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'priorite', 'type_demande', 'client_id', name='uq_sla_policy_scope'),
    )
    op.create_index('ix_sla_policies_tenant_id', 'sla_policies', ['tenant_id'])

    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sla_response_deadline', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('prise_en_charge_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.drop_column('prise_en_charge_at')
        batch_op.drop_column('sla_response_deadline')
    op.drop_index('ix_sla_policies_tenant_id', table_name='sla_policies')
    op.drop_table('sla_policies')
