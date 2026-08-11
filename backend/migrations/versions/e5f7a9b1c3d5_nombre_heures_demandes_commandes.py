"""nombre_heures_demandes_commandes

Le formulaire "Commande" ne permettait de saisir que le nombre d'agents
(`quantite`) — décision produit du 02/08 : l'utilisateur doit aussi pouvoir
saisir un nombre d'heures demandées, indépendamment (les deux champs
peuvent être remplis simultanément, ce n'est pas une alternative exclusive).

Colonne nullable, aucune donnée existante à migrer (les commandes déjà en
base gardent `nombre_heures` à NULL).

Revision ID: e5f7a9b1c3d5
Revises: d4e6f8a0b2c4
Create Date: 2026-08-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f7a9b1c3d5'
down_revision = 'd4e6f8a0b2c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('demandes_commandes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nombre_heures', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('demandes_commandes', schema=None) as batch_op:
        batch_op.drop_column('nombre_heures')
