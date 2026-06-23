"""tenant channels (telephonie/email/chat)

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c0d1e2f3a4b5'
down_revision = 'b9c0d1e2f3a4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('channel_telephonie', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('channel_email', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('channel_chat', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_column('channel_chat')
        batch_op.drop_column('channel_email')
        batch_op.drop_column('channel_telephonie')
