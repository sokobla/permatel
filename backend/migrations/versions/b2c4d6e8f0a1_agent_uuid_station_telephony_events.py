"""agent_uuid_station_telephony_events

Module Téléphonie — corrige un mélange de vocabulaires découvert en audit
(30/07) : `telephony_events.agent_login` contenait l'UUID FusionPBX CC-Agent
pour les événements live ESL (`/events/ingest`), mais l'EXTENSION physique
pour les événements CDR webhook (`/cdr/ingest/<token>`, depuis le correctif
`d5f9e31` du 29/07) — deux identifiants dans la même colonne, jamais
comparables entre eux. Conséquence concrète : la présence live (UUID) et le
volume d'appels CDR (extension) d'un même agent ne se recoupaient plus dans
`/agents/status`, et la résolution nom/poste (`_agent_alias_lookup`, qui
joint sur `User.agent_login` == UUID) échouait silencieusement sur tout
événement CDR, affichant l'identifiant brut au lieu du nom/poste attendu.

Ajoute deux colonnes explicites, sans toucher à `agent_login` (conservée
telle quelle pour compat descendante) :

  - `agent_uuid`               : UUID FusionPBX CC-Agent, peuplé sur les
                                  deux canaux d'ingestion — c'est la colonne
                                  à utiliser pour joindre un événement à un
                                  `User.agent_login`.
  - `agent_station_extension`  : extension physique observée en direct au
                                  moment de l'événement (CDR : profil
                                  originatee du callflow), distincte du
                                  `User.station_extension` déclaratif.

Colonnes nullables, aucune donnée existante à migrer (les événements déjà en
base gardent `agent_uuid`/`agent_station_extension` à NULL — seuls les
nouveaux événements ingérés après ce déploiement seront correctement
distingués).

Revision ID: b2c4d6e8f0a1
Revises: 9c8b7a6f5e4d
Create Date: 2026-07-30 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c4d6e8f0a1'
down_revision = '9c8b7a6f5e4d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agent_uuid', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('agent_station_extension', sa.String(length=20), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_telephony_events_agent_uuid'), ['agent_uuid'], unique=False,
        )


def downgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_telephony_events_agent_uuid'))
        batch_op.drop_column('agent_station_extension')
        batch_op.drop_column('agent_uuid')
