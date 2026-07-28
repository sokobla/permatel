"""add_cdr_webhook_to_pbx_connectors

Module Téléphonie — Phase 14, webhook CDR (FusionPBX mod_json_cdr).

Canal d'ingestion complémentaire à l'ESL live : FusionPBX POSTe un résumé
JSON du call (à la fin de l'appel) vers une URL PERMATEL contenant un jeton
qui résout directement le connecteur. Ajoute sur `pbx_connectors` :

  - `authorized_ip`            : IP(s) autorisée(s) à poster le CDR (texte
                                  libre, vide = pas de restriction).
  - `cdr_webhook_token_hash`   : SHA-256 du jeton, unique/indexé — utilisé
                                  pour la résolution/comparaison (temps
                                  constant côté route), jamais exposé.
  - `cdr_webhook_token`        : copie chiffrée (EncryptedText, même
                                  mécanisme que `password`) — permet de
                                  réafficher le jeton à volonté via le
                                  bouton "Copier le token" (décision
                                  produit : pas un secret à usage unique).

Colonnes nullables, aucune donnée existante à migrer.

Revision ID: 9c8b7a6f5e4d
Revises: 2f54e418e600
Create Date: 2026-07-28 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c8b7a6f5e4d'
down_revision = '2f54e418e600'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pbx_connectors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('authorized_ip', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('cdr_webhook_token_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('cdr_webhook_token', sa.Text(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_pbx_connectors_cdr_webhook_token_hash'), ['cdr_webhook_token_hash'], unique=True,
        )


def downgrade():
    with op.batch_alter_table('pbx_connectors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pbx_connectors_cdr_webhook_token_hash'))
        batch_op.drop_column('cdr_webhook_token')
        batch_op.drop_column('cdr_webhook_token_hash')
        batch_op.drop_column('authorized_ip')
