"""deactivate_on_expiry_user_tokens

Fusionne les deux têtes de migration existantes (c3d4e5f6a7b8, onboarding/
modèles d'email ; b2c4d6e8f0a1, agent_uuid/station téléphonie) et ajoute
`user_tokens.deactivate_on_expiry`.

Décision produit du 31/07 : un admin peut désormais renvoyer un lien
d'onboarding à un utilisateur EXISTANT (compte déjà actif, mot de passe déjà
fonctionnel) — via `POST /users/<id>/onboarding/send` — pas seulement lors de
la création initiale. Contrairement à l'invitation initiale (où la
contrainte produit des 24h puis désactivation reste inchangée, l'utilisateur
n'ayant alors aucun mot de passe utilisable), ignorer ce lien de renvoi ne
doit JAMAIS désactiver un compte qui fonctionnait déjà — seul le jeton
expire, sans effet de bord sur le compte.

`deactivate_on_expiry` porte cette distinction par jeton : True pour
l'invitation initiale (comportement historique, valeur par défaut), False
pour un renvoi vers un utilisateur existant. `onboarding_sweep.py` ne
désactive plus le compte que si le jeton expiré porte `deactivate_on_expiry
= True`.

Colonne NOT NULL avec server_default 'true' : les jetons déjà en base sont
tous des invitations initiales (cette fonctionnalité de renvoi n'existait
pas avant), donc rétro-compatibles avec la valeur par défaut sans ambiguïté.

Revision ID: d4e6f8a0b2c4
Revises: c3d4e5f6a7b8, b2c4d6e8f0a1
Create Date: 2026-07-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e6f8a0b2c4'
down_revision = ('c3d4e5f6a7b8', 'b2c4d6e8f0a1')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_tokens', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'deactivate_on_expiry', sa.Boolean(), nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade():
    with op.batch_alter_table('user_tokens', schema=None) as batch_op:
        batch_op.drop_column('deactivate_on_expiry')
