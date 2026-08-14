"""erp foundations (Phase 6 : ErpConfig, erp_sync_queue, tenant.channel_erp + réglages §4.3)

Fondations transverses de l'intégration ERP (cf. ODOO_INTEGRATION_PLAN.md
§3.B et §5). Trois changements additifs, aucune donnée existante affectée :

1. `erp_config` : une ligne par tenant (company_id ERP + accès direct
   admin chiffré, §4.4) — table neuve, pas de garde data-safety requise.
2. `erp_sync_queue` : file de retry de synchro ERP (§2.1/§2.4), avec
   verrouillage `locked_at`/`locked_until` (absent d'`email_outbox`,
   requis ici car la synchro ERP peut être plus lente/XML-RPC).
3. `tenants.channel_erp` (motif channel_telephonie/email/chat, colonne
   NOT NULL avec server_default sur une table existante) +
   `tenants.document_blocking_expired`/`vacation_delay_threshold_minutes`
   (réglages §4.3, indépendants d'ERP mais posés dès cette phase —
   prérequis Phases 9/10).

Revision ID: c1b16fed65e1
Revises: b7c9e1a3f5d7
Create Date: 2026-08-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'c1b16fed65e1'
down_revision = 'b7c9e1a3f5d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'erp_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('url_erp', sa.Text(), nullable=True),
        sa.Column('admin_username', sa.Text(), nullable=True),
        sa.Column('admin_password', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'],
                                 name='fk_erp_config_tenant_id_tenants', ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', name='uq_erp_config_tenant_id'),
    )
    op.create_index('ix_erp_config_tenant_id', 'erp_config', ['tenant_id'])

    op.create_table(
        'erp_sync_queue',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('flux', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'],
                                 name='fk_erp_sync_queue_tenant_id_tenants', ondelete='CASCADE'),
    )
    op.create_index('ix_erp_sync_queue_tenant_id', 'erp_sync_queue', ['tenant_id'])
    op.create_index('ix_erp_sync_queue_status', 'erp_sync_queue', ['status'])

    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('channel_erp', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('document_blocking_expired', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('vacation_delay_threshold_minutes', sa.Integer(), nullable=False, server_default='15'))


def downgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('vacation_delay_threshold_minutes')
        batch_op.drop_column('document_blocking_expired')
        batch_op.drop_column('channel_erp')

    op.drop_index('ix_erp_sync_queue_status', table_name='erp_sync_queue')
    op.drop_index('ix_erp_sync_queue_tenant_id', table_name='erp_sync_queue')
    op.drop_table('erp_sync_queue')

    op.drop_index('ix_erp_config_tenant_id', table_name='erp_config')
    op.drop_table('erp_config')
