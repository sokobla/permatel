"""missing_composite_fks_sla_prises_emails

Ajoute les FK composites tenant-scopées manquantes, sur le motif déjà utilisé
partout ailleurs dans le schéma (FK(tenant_id, x_id) -> x(tenant_id, id)) :

  - sla_policies.client_id       -> clients(tenant_id, id)
  - prises_de_service.client_id  -> clients(tenant_id, id)   [NOT NULL]
  - prises_de_service.site_id    -> sites(tenant_id, id)
  - emails.demande_id            -> demandes(tenant_id, id)

Ces colonnes n'avaient aucune contrainte (pas même une FK simple), ce qui
permettait un id d'un autre tenant ou un id inexistant.

Garde-fou données :
  - colonnes NULLABLES (client_id sur sla_policies, site_id sur
    prises_de_service, demande_id sur emails) : toute référence orpheline
    est mise à NULL (dégradation sûre — la valeur NULL a déjà un sens
    métier valide : « tous clients », « sans site », « sans demande liée »)
    et journalisée via NOTICE.
  - colonne NOT NULL (prises_de_service.client_id) : impossible de mettre à
    NULL sans perte d'information métier (temps de travail agent) — la
    migration AVORTE avec la liste des lignes orphelines si une seule
    existe, pour résolution manuelle par l'opérateur.

Revision ID: 0cf7c58db304
Revises: a3178519ad55
Create Date: 2026-07-26 00:40:42.129521

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0cf7c58db304'
down_revision = 'a3178519ad55'
branch_labels = None
depends_on = None


def _nullify_orphans(child_table, child_fk_col, parent_table):
    """Met à NULL les références orphelines (dégradation sûre, colonne nullable)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        UPDATE {child_table} c
        SET {child_fk_col} = NULL
        WHERE c.{child_fk_col} IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {parent_table} p
              WHERE p.tenant_id = c.tenant_id AND p.id = c.{child_fk_col}
          )
    """))
    if result.rowcount:
        print(
            f"  ATTENTION  {result.rowcount} référence(s) orpheline(s) "
            f"'{child_table}.{child_fk_col}' -> '{parent_table}' mise(s) à NULL."
        )


def _abort_if_orphans(child_table, child_fk_col, parent_table):
    """Avorte la migration si des références orphelines existent (colonne NOT NULL)."""
    conn = op.get_bind()
    if rows := conn.execute(sa.text(f"""
        SELECT c.id FROM {child_table} c
        WHERE NOT EXISTS (
            SELECT 1 FROM {parent_table} p
            WHERE p.tenant_id = c.tenant_id AND p.id = c.{child_fk_col}
        )
    """)).fetchall():
        ids = ", ".join(str(r[0]) for r in rows)
        raise RuntimeError(
            f"Migration {revision} interrompue : {len(rows)} ligne(s) dans "
            f"'{child_table}' référencent un(e) '{parent_table}' inexistant(e) "
            f"ou d'un autre tenant via '{child_fk_col}' (ids: {ids}). "
            f"Corrigez ces données avant de relancer 'flask db upgrade heads'."
        )


def upgrade():
    # ── sla_policies.client_id (nullable) -> clients(tenant_id, id) ────────
    _nullify_orphans("sla_policies", "client_id", "clients")
    with op.batch_alter_table("sla_policies", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_sla_policies_client_tenant", "clients",
            ["tenant_id", "client_id"], ["tenant_id", "id"],
        )

    # ── prises_de_service.client_id (NOT NULL) -> clients(tenant_id, id) ───
    _abort_if_orphans("prises_de_service", "client_id", "clients")
    with op.batch_alter_table("prises_de_service", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_prises_de_service_client_tenant", "clients",
            ["tenant_id", "client_id"], ["tenant_id", "id"],
        )

    # ── prises_de_service.site_id (nullable) -> sites(tenant_id, id) ───────
    _nullify_orphans("prises_de_service", "site_id", "sites")
    with op.batch_alter_table("prises_de_service", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_prises_de_service_site_tenant", "sites",
            ["tenant_id", "site_id"], ["tenant_id", "id"],
        )

    # ── emails.demande_id (nullable) -> demandes(tenant_id, id) ────────────
    _nullify_orphans("emails", "demande_id", "demandes")
    with op.batch_alter_table("emails", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_emails_demande_tenant", "demandes",
            ["tenant_id", "demande_id"], ["tenant_id", "id"],
        )


def downgrade():
    with op.batch_alter_table("emails", schema=None) as batch_op:
        batch_op.drop_constraint("fk_emails_demande_tenant", type_="foreignkey")

    with op.batch_alter_table("prises_de_service", schema=None) as batch_op:
        batch_op.drop_constraint("fk_prises_de_service_site_tenant", type_="foreignkey")
        batch_op.drop_constraint("fk_prises_de_service_client_tenant", type_="foreignkey")

    with op.batch_alter_table("sla_policies", schema=None) as batch_op:
        batch_op.drop_constraint("fk_sla_policies_client_tenant", type_="foreignkey")
