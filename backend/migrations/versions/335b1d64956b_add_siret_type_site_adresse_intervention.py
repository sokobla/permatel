"""add_siret_type_site_adresse_intervention

Revision ID: 335b1d64956b
Revises: 43ae77b7e04d
Create Date: 2026-06-16 14:32:05.345460

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '335b1d64956b'
down_revision = '43ae77b7e04d'
branch_labels = None
depends_on = None


def _column_exists(table_name, column_name):
    """Vérifie si une colonne existe déjà dans la table (guard idempotent)."""
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Guard idempotent : on n'ajoute chaque colonne que si elle est absente.
    # Cela permet de rejouer la migration sans erreur DuplicateColumn lorsqu'une
    # exécution précédente a échoué en cours de route (ex: crash partiel).

    # --- Table clients ---
    if not _column_exists('clients', 'siret'):
        with op.batch_alter_table('clients', schema=None) as batch_op:
            batch_op.add_column(sa.Column('siret', sa.String(length=14), nullable=True))

    # --- Table demandes ---
    if not _column_exists('demandes', 'adresse_intervention'):
        with op.batch_alter_table('demandes', schema=None) as batch_op:
            batch_op.add_column(sa.Column('adresse_intervention', sa.String(length=300), nullable=True))

    # --- Table sites ---
    if not _column_exists('sites', 'type_site'):
        with op.batch_alter_table('sites', schema=None) as batch_op:
            batch_op.add_column(sa.Column('type_site', sa.String(length=50), nullable=True))


def downgrade():
    # Guard idempotent en descente : on ne supprime que si la colonne existe.
    if _column_exists('sites', 'type_site'):
        with op.batch_alter_table('sites', schema=None) as batch_op:
            batch_op.drop_column('type_site')

    if _column_exists('demandes', 'adresse_intervention'):
        with op.batch_alter_table('demandes', schema=None) as batch_op:
            batch_op.drop_column('adresse_intervention')

    if _column_exists('clients', 'siret'):
        with op.batch_alter_table('clients', schema=None) as batch_op:
            batch_op.drop_column('siret')
