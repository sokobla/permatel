"""notifications + email_outbox + flags d'alerte SLA

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-23 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'f3a4b5c6d7e8'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False, server_default='normal'),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_tenant_id', 'notifications', ['tenant_id'])
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])

    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('in_app', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('email', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id', 'type', name='uq_notif_pref'),
    )

    op.create_table(
        'email_outbox',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('to_address', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=300), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_outbox_tenant_id', 'email_outbox', ['tenant_id'])
    op.create_index('ix_email_outbox_status', 'email_outbox', ['status'])

    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sla_warning_notified', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('sla_breach_notified', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.drop_column('sla_breach_notified')
        batch_op.drop_column('sla_warning_notified')
    op.drop_index('ix_email_outbox_status', table_name='email_outbox')
    op.drop_index('ix_email_outbox_tenant_id', table_name='email_outbox')
    op.drop_table('email_outbox')
    op.drop_table('notification_preferences')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_index('ix_notifications_tenant_id', table_name='notifications')
    op.drop_table('notifications')
