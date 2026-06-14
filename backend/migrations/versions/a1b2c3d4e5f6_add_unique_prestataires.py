"""Add unique constraint on prestataires tenant_id + id

Revision ID: a1b2c3d4e5f6
Revises: 346eee837e1a
Create Date: 2026-04-27 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '28f81a092a32'
branch_labels = None
depends_on = None


def upgrade():
    # Add unique constraint on (tenant_id, id) for composite foreign key support
    # These are needed because the subsequent migration creates composite foreign keys
    # referencing (tenant_id, id) in these tables
    with op.batch_alter_table('prestataires', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_prestataires_tenant_id', ['tenant_id', 'id'])

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_clients_tenant_id', ['tenant_id', 'id'])

    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_sites_tenant_id', ['tenant_id', 'id'])

    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_demandes_tenant_id', ['tenant_id', 'id'])


def downgrade():
    # Ordre correct pour downgrade (sans DROP CASCADE):
    # 1) Drop des FK composites qui dépendent des contraintes uniques
    # 2) Drop des contraintes uniques ajoutées en upgrade
    # 3) Re-création des FK simples précédents (client_id -> clients.id, demande_id -> demandes.id)
    # Hypothèses :
    # - 'demandes' a les colonnes 'tenant_id' (UUID) et 'client_id' (Integer)
    # - 'sites' a les colonnes 'tenant_id' (UUID) et 'client_id' (Integer)
    # - noms des contraintes composites créées ultérieurement :
    #     'fk_demandes_client_tenant', 'fk_demandes_site_tenant', 'fk_sites_client_tenant'
    # Ajustez les noms si vos contraintes réelles diffèrent.

    # 1) Drop des FK composites dépendantes
    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_demandes_client_tenant', type_='foreignkey')
        batch_op.drop_constraint('fk_demandes_site_tenant', type_='foreignkey')

    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sites_client_tenant', type_='foreignkey')

    # Drop autres FK qui référencent demandes si elles sont des FK composites
    with op.batch_alter_table('fichiers', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('fk_fichiers_demande_tenant', type_='foreignkey')
        except Exception:
            # ignore si n'existe pas
            pass

    with op.batch_alter_table('interactions', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('fk_interactions_demande_tenant', type_='foreignkey')
        except Exception:
            pass

    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('fk_telephony_events_demande_tenant', type_='foreignkey')
        except Exception:
            pass

    # 2) Drop des contraintes uniques ajoutées
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_constraint('uq_clients_tenant_id', type_='unique')

    with op.batch_alter_table('prestataires', schema=None) as batch_op:
        batch_op.drop_constraint('uq_prestataires_tenant_id', type_='unique')

    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.drop_constraint('uq_sites_tenant_id', type_='unique')

    with op.batch_alter_table('demandes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_demandes_tenant_id', type_='unique')

    # 3) Re-créer les FK simples précédents
    # Recreate client_id -> clients.id
    op.create_foreign_key(
        'fk_demandes_client_id',
        'demandes', 'clients',
        local_cols=['client_id'], remote_cols=['id'],
    )

    op.create_foreign_key(
        'fk_sites_client_id',
        'sites', 'clients',
        local_cols=['client_id'], remote_cols=['id'],
    )

    # Recreate demandes -> fichiers/interactions/telephony simple FKs if needed
    try:
        op.create_foreign_key('fk_fichiers_demande_id', 'fichiers', 'demandes', ['demande_id'], ['id'])
    except Exception:
        pass

    try:
        op.create_foreign_key('fk_interactions_demande_id', 'interactions', 'demandes', ['demande_id'], ['id'])
    except Exception:
        pass

    try:
        op.create_foreign_key('fk_telephony_events_demande_id', 'telephony_events', 'demandes', ['demande_id'], ['id'])
    except Exception:
        pass