"""tenant_invitations + bascule username=email + membership_role default

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Table des invitations d'onboarding
    op.create_table(
        'tenant_invitations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('membership_role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('invited_by_user_id', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_tenant_invitations_token'),
    )
    op.create_index('ix_tenant_invitations_tenant_id', 'tenant_invitations', ['tenant_id'])
    op.create_index('ix_tenant_invitations_email', 'tenant_invitations', ['email'])
    op.create_index('ix_tenant_invitations_status', 'tenant_invitations', ['status'])

    # 2. username = email : élargir la colonne puis aligner les données existantes
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(length=50),
                              type_=sa.String(length=120), existing_nullable=False)
    op.execute("UPDATE users SET username = email WHERE username <> email")

    # 3. membership_role : valeur par défaut pour les lignes existantes
    op.execute("UPDATE tenant_users SET membership_role = 'member' WHERE membership_role IS NULL")


def downgrade():
    op.execute("UPDATE tenant_users SET membership_role = NULL WHERE membership_role = 'member'")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('username', existing_type=sa.String(length=120),
                              type_=sa.String(length=50), existing_nullable=False)
    op.drop_index('ix_tenant_invitations_status', table_name='tenant_invitations')
    op.drop_index('ix_tenant_invitations_email', table_name='tenant_invitations')
    op.drop_index('ix_tenant_invitations_tenant_id', table_name='tenant_invitations')
    op.drop_table('tenant_invitations')
