"""ended_by_id_prises_de_service

Rapport des prises de service (14/08) : ajoute `prises_de_service.ended_by_id`,
symétrique à `created_by_id` déjà présent — permet de distinguer l'utilisateur
PERMATEL ayant déclaré le DÉBUT de celui ayant déclaré la FIN d'une vacation
(les deux peuvent différer : changement d'équipe, clôture par un superviseur
différent de celui qui a ouvert la vacation).

Colonne additive pure, nullable (aucune valeur historique connue pour les
vacations déjà closes avant ce chantier — laissée NULL, pas de backfill
possible).

Revision ID: b7c9e1a3f5d7
Revises: af1a8735c279
Create Date: 2026-08-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c9e1a3f5d7'
down_revision = 'af1a8735c279'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prises_de_service', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ended_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_prises_de_service_ended_by_id_users',
            'users', ['ended_by_id'], ['id'], ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('prises_de_service', schema=None) as batch_op:
        batch_op.drop_constraint('fk_prises_de_service_ended_by_id_users', type_='foreignkey')
        batch_op.drop_column('ended_by_id')
