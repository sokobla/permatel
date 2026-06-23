"""replace_type_commande_enum_security_missions

Revision ID: 0e05af69b750
Revises: c782f962779a
Create Date: 2026-06-18 13:49:34.469861

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e05af69b750'
down_revision = 'c782f962779a'
branch_labels = None
depends_on = None

# Anciennes valeurs IT/achats → converties en 'autre'
OLD_VALUES = ('achat', 'renouvellement', 'maintenance', 'licence', 'consultation')


def upgrade():
    # Aucun changement DDL : la colonne est VARCHAR (native_enum=False).
    # On convertit les éventuelles anciennes valeurs en 'autre'.
    op.execute(
        f"""
        UPDATE demandes_commandes
        SET type_commande = 'autre'
        WHERE type_commande IN ({', '.join(f"'{v}'" for v in OLD_VALUES)})
        """
    )


def downgrade():
    # Impossible de retrouver la valeur d'origine — on laisse 'autre'.
    pass
