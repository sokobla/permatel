"""pause_code_and_pbx_pause_codes

Module Téléphonie — exécution à distance ESL (login/logout/statut agent) et
codes de pause (13/08).

Ajoute :
  - `telephony_events.pause_code` : sous-statut de pause à 1 chiffre, porté
    par l'événement CUSTOM `agent_pause_code` émis par le connecteur au
    passage en "On Break".
  - `pbx_pause_codes` : table de correspondance des codes de pause,
    configurable par tenant (Paramètres > Téléphonie). Pas de seed ici — la
    ligne protégée "0" est créée à la volée au premier accès pour un tenant
    donné (cf. `backend/app/routes/telephony.py`), pour couvrir aussi bien
    les tenants existants que futurs sans dépendre d'un hook de création de
    tenant.

Deux changements additifs purs, aucune donnée existante à migrer.

Revision ID: af1a8735c279
Revises: e5f7a9b1c3d5
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'af1a8735c279'
down_revision = 'e5f7a9b1c3d5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pause_code', sa.String(length=50), nullable=True))

    op.create_table(
        'pbx_pause_codes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('digit', sa.String(length=1), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('is_protected', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('tenant_id', 'digit', name='uq_pbx_pause_code_tenant_digit'),
    )
    with op.batch_alter_table('pbx_pause_codes', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_pbx_pause_codes_tenant_id'), ['tenant_id'], unique=False
        )


def downgrade():
    with op.batch_alter_table('pbx_pause_codes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pbx_pause_codes_tenant_id'))
    op.drop_table('pbx_pause_codes')

    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_column('pause_code')
