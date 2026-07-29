"""add_linked_call_uuid_to_telephony_events

Module Téléphonie — corrélation des legs d'un appel bridgé (Supervision >
Téléphonie).

Confirmé sur trafic FreeSWITCH réel (29/07) : un appel physique bridgé
produit deux `call_uuid` PERMATEL distincts (un par leg), chacun avec son
propre `Unique-ID` FreeSWITCH. Le header `Other-Leg-Unique-ID` n'est vide
QUE tant que le pont n'est pas établi (confirmé sur un appel jamais
décroché) — une fois `CHANNEL_ANSWER` atteint sur les deux legs d'un pont
direct agent<->externe, il porte bien l'identifiant de l'autre leg. Cette
colonne capte cette valeur pour permettre à `/active-calls` de fusionner
les deux lignes en une seule (voir routes/telephony.py).

Fusion aussi avec e9f0a1b2c3d4 (têtes multiples existantes).

Colonne nullable, aucune donnée existante à migrer.

Revision ID: a4b5c6d7e8f9
Revises: 9c8b7a6f5e4d, e9f0a1b2c3d4
Create Date: 2026-07-29 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4b5c6d7e8f9'
down_revision = ('9c8b7a6f5e4d', 'e9f0a1b2c3d4')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('linked_call_uuid', sa.String(length=100), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_telephony_events_linked_call_uuid'), ['linked_call_uuid'], unique=False
        )


def downgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_telephony_events_linked_call_uuid'))
        batch_op.drop_column('linked_call_uuid')
