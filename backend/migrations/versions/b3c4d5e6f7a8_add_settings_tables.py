"""add settings tables (smtp_settings, reference_values)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'smtp_settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=False, server_default='587'),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password', sa.String(length=255), nullable=True),
        sa.Column('from_address', sa.String(length=255), nullable=True),
        sa.Column('security', sa.String(length=10), nullable=False, server_default='tls'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', name='uq_smtp_settings_tenant'),
    )
    op.create_index('ix_smtp_settings_tenant_id', 'smtp_settings', ['tenant_id'])

    op.create_table(
        'reference_values',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('family', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=150), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', 'family', 'label', name='uq_refval_tenant_family_label'),
    )
    op.create_index('ix_reference_values_tenant_id', 'reference_values', ['tenant_id'])
    op.create_index('ix_reference_values_family', 'reference_values', ['family'])


def downgrade():
    op.drop_index('ix_reference_values_family', table_name='reference_values')
    op.drop_index('ix_reference_values_tenant_id', table_name='reference_values')
    op.drop_table('reference_values')
    op.drop_index('ix_smtp_settings_tenant_id', table_name='smtp_settings')
    op.drop_table('smtp_settings')
