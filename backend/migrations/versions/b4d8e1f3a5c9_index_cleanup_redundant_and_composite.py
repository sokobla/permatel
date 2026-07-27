"""index_cleanup_redundant_and_composite

Nettoyage d'index :

  - Supprime 3 index simple-colonne redevenus redondants depuis l'ajout des
    contraintes uniques composites `(tenant_id, code)` : `ix_clients_code_client`,
    `ix_sites_code_site`, `ix_agents_securite_matricule`. Chacune de ces
    contraintes crée déjà un index B-tree composite qui sert entièrement les
    lookups tenant-scopés (le seul pattern de requête utilisé par l'app) ;
    l'index simple-colonne ne fait plus que coûter de l'espace/maintenance à
    chaque INSERT/UPDATE sans jamais être le meilleur plan pour une requête
    filtrée par tenant.
  - Ajoute un index composite `(tenant_id, statut, created_at)` sur `demandes`
    pour accélérer la requête la plus courante de l'app : « demandes ouvertes
    de ce tenant, triées par priorité/date » (Workspace, dashboard).

Revision ID: b4d8e1f3a5c9
Revises: f1a4c9e6b2d7
Create Date: 2026-07-26 02:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b4d8e1f3a5c9'
down_revision = 'f1a4c9e6b2d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.drop_index("ix_clients_code_client")

    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.drop_index("ix_sites_code_site")

    with op.batch_alter_table("agents_securite", schema=None) as batch_op:
        batch_op.drop_index("ix_agents_securite_matricule")

    with op.batch_alter_table("demandes", schema=None) as batch_op:
        batch_op.create_index(
            "ix_demandes_tenant_statut_created",
            ["tenant_id", "statut", "created_at"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("demandes", schema=None) as batch_op:
        batch_op.drop_index("ix_demandes_tenant_statut_created")

    with op.batch_alter_table("agents_securite", schema=None) as batch_op:
        batch_op.create_index("ix_agents_securite_matricule", ["matricule"], unique=False)

    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.create_index("ix_sites_code_site", ["code_site"], unique=False)

    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.create_index("ix_clients_code_client", ["code_client"], unique=False)
