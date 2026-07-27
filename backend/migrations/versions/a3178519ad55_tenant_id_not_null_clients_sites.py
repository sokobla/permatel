"""tenant_id_not_null_clients_sites

Durcit l'isolation multi-tenant : clients.tenant_id et sites.tenant_id
deviennent NOT NULL, alignés sur toutes les autres tables tenant-scopées
(demandes, interactions, fichiers, agents_securite, emails, notifications,
sla_policies) qui l'imposaient déjà.

Garde-fou : si des lignes avec tenant_id NULL existent encore (import
défectueux, bug applicatif passé), la migration AVORTE avec la liste des
identifiants concernés plutôt que de deviner un tenant ou de supprimer des
données métier. L'opérateur doit résoudre manuellement (assigner le bon
tenant ou désactiver/supprimer la ligne) puis relancer la migration.

Revision ID: a3178519ad55
Revises: a7fa67a8b0be
Create Date: 2026-07-26 00:40:30.847530

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3178519ad55'
down_revision = 'a7fa67a8b0be'
branch_labels = None
depends_on = None


def _abort_if_null_tenant(table_name: str) -> None:
    conn = op.get_bind()
    if rows := conn.execute(
        sa.text(f"SELECT id FROM {table_name} WHERE tenant_id IS NULL")
    ).fetchall():
        ids = ", ".join(str(r[0]) for r in rows)
        raise RuntimeError(
            f"Migration {revision} interrompue : {len(rows)} ligne(s) dans "
            f"'{table_name}' ont tenant_id NULL (ids: {ids}). "
            f"Assignez un tenant valide (ou désactivez/supprimez ces lignes) "
            f"avant de relancer 'flask db upgrade heads'."
        )


def upgrade():
    # Garde-fou données AVANT de poser la contrainte NOT NULL.
    _abort_if_null_tenant("clients")
    _abort_if_null_tenant("sites")

    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.UUID(), nullable=False)

    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.UUID(), nullable=False)


def downgrade():
    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.UUID(), nullable=True)

    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.UUID(), nullable=True)
