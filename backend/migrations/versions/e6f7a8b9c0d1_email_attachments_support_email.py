"""email_attachments table + tenants.support_email

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-06-21 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('support_email', sa.String(length=255), nullable=True))

    op.create_table(
        'email_attachments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('email_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=120), nullable=True),
        sa.Column('size', sa.Integer(), nullable=True),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_email_attachments_email_id', 'email_attachments', ['email_id'])
    op.create_index('ix_email_attachments_tenant_id', 'email_attachments', ['tenant_id'])


def downgrade():
    op.drop_index('ix_email_attachments_tenant_id', table_name='email_attachments')
    op.drop_index('ix_email_attachments_email_id', table_name='email_attachments')
    op.drop_table('email_attachments')
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('support_email')
