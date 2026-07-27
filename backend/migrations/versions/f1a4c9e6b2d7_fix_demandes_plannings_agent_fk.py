"""fix_demandes_plannings_agent_fk

Corrige un bug de FK confirmé : `demandes_plannings.agent_concerne_id` et
`demandes_plannings.agent_remplacant_id` référencent en base `users(id)`
(dernière migration à les avoir touchées : c5e10bf50c26_use_varchar_for_enums,
qui recrée ces deux FK vers 'users' au lieu de 'agents_securite'), alors que
le modèle ORM (`app/models/demande.py::DemandePlanning`) déclare depuis
toujours `ForeignKey('agents_securite.id')`.

`users.id` et `agents_securite.id` sont tous deux des entiers auto-incrémentés
à partir de 1 : une `DemandePlanning` référençant l'agent id=3 passait la
contrainte tant qu'un *utilisateur* id=3 existait, sans jamais valider contre
`agents_securite` — cassant silencieusement l'intégrité référentielle (et,
potentiellement, l'isolation tenant si l'id substitué appartient à un tenant
différent).

Garde-fou données : toute valeur agent_concerne_id/agent_remplacant_id qui ne
correspond à aucune ligne de `agents_securite` est mise à NULL (dégradation
sûre — colonnes nullables, NULL a déjà un sens métier valide : « non
renseigné ») et journalisée, avant de poser la FK correcte.

Revision ID: f1a4c9e6b2d7
Revises: 0cf7c58db304
Create Date: 2026-07-26 00:41:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a4c9e6b2d7'
down_revision = '0cf7c58db304'
branch_labels = None
depends_on = None

_OLD_FK_NAMES = {
    "agent_concerne_id": "demandes_plannings_agent_concerne_id_fkey",
    "agent_remplacant_id": "demandes_plannings_agent_remplacant_id_fkey",
}
_NEW_FK_NAMES = {
    "agent_concerne_id": "fk_demandes_plannings_agent_concerne",
    "agent_remplacant_id": "fk_demandes_plannings_agent_remplacant",
}


def _nullify_orphans(column: str) -> None:
    """Met à NULL les références qui ne correspondent à aucun agent réel."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"""
        UPDATE demandes_plannings
        SET {column} = NULL
        WHERE {column} IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM agents_securite a WHERE a.id = demandes_plannings.{column}
          )
    """))
    if result.rowcount:
        print(
            f"  ATTENTION  {result.rowcount} référence(s) orpheline(s) "
            f"'demandes_plannings.{column}' -> 'agents_securite' mise(s) à NULL "
            f"(pointaient vers un id inexistant dans agents_securite — probable "
            f"séquelle du bug de FK historique vers 'users')."
        )


def upgrade():
    _nullify_orphans("agent_concerne_id")
    _nullify_orphans("agent_remplacant_id")

    with op.batch_alter_table("demandes_plannings", schema=None) as batch_op:
        batch_op.drop_constraint(_OLD_FK_NAMES["agent_concerne_id"], type_="foreignkey")
        batch_op.drop_constraint(_OLD_FK_NAMES["agent_remplacant_id"], type_="foreignkey")
        batch_op.create_foreign_key(
            _NEW_FK_NAMES["agent_concerne_id"], "agents_securite",
            ["agent_concerne_id"], ["id"],
        )
        batch_op.create_foreign_key(
            _NEW_FK_NAMES["agent_remplacant_id"], "agents_securite",
            ["agent_remplacant_id"], ["id"],
        )


def downgrade():
    with op.batch_alter_table("demandes_plannings", schema=None) as batch_op:
        batch_op.drop_constraint(_NEW_FK_NAMES["agent_remplacant_id"], type_="foreignkey")
        batch_op.drop_constraint(_NEW_FK_NAMES["agent_concerne_id"], type_="foreignkey")
        batch_op.create_foreign_key(
            _OLD_FK_NAMES["agent_remplacant_id"], "users",
            ["agent_remplacant_id"], ["id"],
        )
        batch_op.create_foreign_key(
            _OLD_FK_NAMES["agent_concerne_id"], "users",
            ["agent_concerne_id"], ["id"],
        )
