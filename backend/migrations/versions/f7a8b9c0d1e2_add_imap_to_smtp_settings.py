"""add imap fields to smtp_settings (réception Phase 2)

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-06-21 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('smtp_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('imap_host', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('imap_port', sa.Integer(), nullable=False, server_default='993'))
        batch_op.add_column(sa.Column('imap_security', sa.String(length=10), nullable=False, server_default='ssl'))
        batch_op.add_column(sa.Column('imap_username', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('imap_password', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('inbound_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('smtp_settings', schema=None) as batch_op:
        batch_op.drop_column('inbound_enabled')
        batch_op.drop_column('imap_password')
        batch_op.drop_column('imap_username')
        batch_op.drop_column('imap_security')
        batch_op.drop_column('imap_port')
        batch_op.drop_column('imap_host')
