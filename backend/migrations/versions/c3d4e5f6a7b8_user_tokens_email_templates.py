"""user_tokens (onboarding + reset mdp) + email_templates + users.onboarding_status

Revision ID: c3d4e5f6a7b8
Revises: a4b5c6d7e8f9
Create Date: 2026-07-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = 'c3d4e5f6a7b8'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Jetons utilisateur (onboarding + réinitialisation de mot de passe) —
    # une seule table pour les deux usages, discriminée par `purpose` (même
    # mécanique de génération/hash/validation, seule la durée de vie diffère).
    op.create_table(
        'user_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=20), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_user_tokens_token'),
    )
    op.create_index('ix_user_tokens_user_id', 'user_tokens', ['user_id'])
    op.create_index('ix_user_tokens_purpose', 'user_tokens', ['purpose'])
    op.create_index('ix_user_tokens_status', 'user_tokens', ['status'])

    # 2. Modèles d'email personnalisables par tenant (Paramètres > Emails).
    # Une ligne absente ou is_active=False retombe sur le défaut système
    # (app/utils/email_templates.py::SYSTEM_DEFAULTS) — jamais bloquant.
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('template_key', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'template_key', name='uq_email_templates_tenant_key'),
    )
    op.create_index('ix_email_templates_tenant_id', 'email_templates', ['tenant_id'])
    op.create_index('ix_email_templates_template_key', 'email_templates', ['template_key'])

    # 3. Statut d'onboarding sur User (dénormalisé depuis le dernier UserToken
    # purpose="onboarding" — évite une jointure à chaque rendu du tableau).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('onboarding_status', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('onboarding_status')

    op.drop_index('ix_email_templates_template_key', table_name='email_templates')
    op.drop_index('ix_email_templates_tenant_id', table_name='email_templates')
    op.drop_table('email_templates')

    op.drop_index('ix_user_tokens_status', table_name='user_tokens')
    op.drop_index('ix_user_tokens_purpose', table_name='user_tokens')
    op.drop_index('ix_user_tokens_user_id', table_name='user_tokens')
    op.drop_table('user_tokens')
