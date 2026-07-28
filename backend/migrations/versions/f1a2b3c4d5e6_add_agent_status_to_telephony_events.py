"""add_agent_status_to_telephony_events

Module Téléphonie — support de la grille d'état des agents (Supervision >
Téléphonie, Phase 13).

Jusqu'ici, l'événement `CALLCENTER_AGENT_STATE_CHANGE` (mod_callcenter) était
capté sans son statut réel : le header FreeSWITCH `CC-Agent-Status`
("Available", "On Break", "Logged Out", …) n'était pas remonté par le
connecteur, ce qui interdisait d'afficher une présence agent honnête (le
choix précédent était de ne montrer aucune présence plutôt que d'en
fabriquer une). Ce correctif capte la valeur brute et l'expose telle quelle
(normalisation en ligne/pause/hors-ligne faite côté route, pas ici).

Colonne nullable, aucune donnée existante à migrer.

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-07-28 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agent_status', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_column('agent_status')
