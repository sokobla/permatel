"""extend_telephony_events

Module Téléphonie — Phase 11 (fondations backend), tâche 11.1.

Étend la table `telephony_events` (posée mais dormante jusqu'ici — aucune
route/service ne l'alimentait) pour couvrir le besoin du connecteur PBX :

  - `pbx_connector_id`  : PBX émetteur (nouveau, FK vers pbx_connectors,
                          nullable — un événement historique sans connecteur
                          identifié reste valide).
  - `call_direction`, `callee_number`, `agent_login`, `queue_id`,
    `recording_url`, `raw_payload` (JSONB) : nouveaux champs du besoin V1.
  - `call_status`       : nouveau, statut d'appel normalisé.
  - `event_type`        : élargi d'un enum Postgres figé à 4 valeurs
                          (CALL_START/END/TRANSFER/HOLD) vers un `String`
                          libre — le besoin réel couvre 6+ valeurs
                          (CHANNEL_CREATE/PROGRESS_MEDIA/ANSWER/
                          HANGUP_COMPLETE, CALLCENTER_QUEUE_ENTER,
                          CALLCENTER_AGENT_STATE_CHANGE) et une phase 2
                          Asterisk en ajoutera d'autres encore — même
                          traitement que la migration c5e10bf50c26
                          (use_varchar_for_enums), pour ne plus jamais avoir
                          à migrer le schéma pour une nouvelle valeur
                          d'événement PBX.
  - `user_session_id`   : passe de NOT NULL à nullable — un événement PBX se
                          rattache directement à `agent_login` (nouveau
                          champ dénormalisé), le rattachement à une session
                          active devient optionnel plutôt qu'obligatoire.

Garde-fou données : la conversion d'enum vers String est un simple
changement de représentation (les 4 valeurs existantes restent valides en
tant que chaînes) — aucune perte de données possible, pas de garde-fou
nécessaire au sens propre. La colonne `user_session_id` s'assouplit
(NOT NULL -> nullable), ce qui ne peut jamais casser de ligne existante.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-28 00:00:10.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None

_OLD_EVENT_TYPE_ENUM = postgresql.ENUM(
    'CALL_START', 'CALL_END', 'CALL_TRANSFER', 'CALL_HOLD', name='eventtype'
)
# JSONB en PostgreSQL, repli JSON générique sous SQLite (tests) — même motif
# que JSONB_VARIANT dans app/models/demande.py.
_JSONB_VARIANT = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pbx_connector_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('call_direction', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('call_status', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('callee_number', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('agent_login', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('queue_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('recording_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('raw_payload', _JSONB_VARIANT, nullable=True))

        batch_op.alter_column('user_session_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column(
            'event_type',
            existing_type=_OLD_EVENT_TYPE_ENUM,
            type_=sa.String(length=50),
            existing_nullable=False,
            postgresql_using='event_type::text',
        )

        batch_op.create_foreign_key(
            'fk_telephony_events_pbx_connector', 'pbx_connectors',
            ['pbx_connector_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_index(batch_op.f('ix_telephony_events_pbx_connector_id'), ['pbx_connector_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_telephony_events_agent_login'), ['agent_login'], unique=False)
        batch_op.create_index(batch_op.f('ix_telephony_events_queue_id'), ['queue_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_telephony_events_call_uuid'), ['call_uuid'], unique=False)

    # Le type enum Postgres 'eventtype' n'est plus référencé par aucune
    # colonne (event_type est désormais un String) : le supprimer.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE eventtype')


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        _OLD_EVENT_TYPE_ENUM.create(bind, checkfirst=True)

    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_telephony_events_call_uuid'))
        batch_op.drop_index(batch_op.f('ix_telephony_events_queue_id'))
        batch_op.drop_index(batch_op.f('ix_telephony_events_agent_login'))
        batch_op.drop_index(batch_op.f('ix_telephony_events_pbx_connector_id'))
        batch_op.drop_constraint('fk_telephony_events_pbx_connector', type_='foreignkey')

        batch_op.alter_column(
            'event_type',
            existing_type=sa.String(length=50),
            type_=_OLD_EVENT_TYPE_ENUM,
            existing_nullable=False,
            postgresql_using='event_type::eventtype',
        )
        batch_op.alter_column('user_session_id', existing_type=sa.Integer(), nullable=False)

        batch_op.drop_column('raw_payload')
        batch_op.drop_column('recording_url')
        batch_op.drop_column('queue_id')
        batch_op.drop_column('agent_login')
        batch_op.drop_column('callee_number')
        batch_op.drop_column('call_status')
        batch_op.drop_column('call_direction')
        batch_op.drop_column('pbx_connector_id')
