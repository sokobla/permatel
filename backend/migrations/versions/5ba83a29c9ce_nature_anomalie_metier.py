"""nature_anomalie_metier

Revision ID: 5ba83a29c9ce
Revises: f25dc29abb83
Create Date: 2026-06-18 21:40:52.807332

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ba83a29c9ce'
down_revision = 'f25dc29abb83'
branch_labels = None
depends_on = None

_NEW = sa.Enum(
    'ANJ', 'ABSENCE_JUSTIFIEE', 'RETARD_PRISE_SERVICE', 'AGENT_NON_SUR_SITE',
    'DOUBLON_PLANNING', 'REMPLACEMENT_PERMUTATION', 'MODIFICATION_VACATION',
    'PROBLEME_TECHNIQUE', 'SITE_PRESTATAIRE_INJOIGNABLE', 'BLOCAGE_OUTIL_RH',
    'DEMANDE_DE_RENFORT', 'ANOMALIE_FACTURATION', 'AUTRE',
    name='nature_anomalie_enum', native_enum=False,
)
_OLD = sa.VARCHAR(length=20)


def upgrade():
    with op.batch_alter_table('demandes_anomalies', schema=None) as batch_op:
        batch_op.alter_column('nature_anomalie',
               existing_type=_OLD, type_=_NEW, existing_nullable=True)


def downgrade():
    with op.batch_alter_table('demandes_anomalies', schema=None) as batch_op:
        batch_op.alter_column('nature_anomalie',
               existing_type=_NEW, type_=_OLD, existing_nullable=True)
