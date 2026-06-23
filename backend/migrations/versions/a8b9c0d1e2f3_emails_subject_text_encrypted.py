"""emails.subject -> TEXT (chiffrement du contenu)

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-06-21 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('emails', schema=None) as batch_op:
        batch_op.alter_column('subject', existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)


def downgrade():
    with op.batch_alter_table('emails', schema=None) as batch_op:
        batch_op.alter_column('subject', existing_type=sa.Text(), type_=sa.String(length=500), existing_nullable=True)
