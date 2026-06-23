"""add emails table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'emails',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='sent'),
        sa.Column('message_id', sa.String(length=255), nullable=True),
        sa.Column('in_reply_to', sa.String(length=255), nullable=True),
        sa.Column('thread_id', sa.String(length=255), nullable=True),
        sa.Column('from_address', sa.String(length=255), nullable=True),
        sa.Column('to_addresses', sa.Text(), nullable=True),
        sa.Column('cc', sa.Text(), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('demande_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('imap_uid', sa.String(length=64), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('has_attachments', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_emails_tenant_id', 'emails', ['tenant_id'])
    op.create_index('ix_emails_direction', 'emails', ['direction'])
    op.create_index('ix_emails_status', 'emails', ['status'])
    op.create_index('ix_emails_contact_id', 'emails', ['contact_id'])
    op.create_index('ix_emails_thread_id', 'emails', ['thread_id'])


def downgrade():
    for ix in ('ix_emails_thread_id', 'ix_emails_contact_id', 'ix_emails_status',
               'ix_emails_direction', 'ix_emails_tenant_id'):
        op.drop_index(ix, table_name='emails')
    op.drop_table('emails')
