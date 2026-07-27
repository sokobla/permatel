"""pbx_connector_tenant_scoping

Module Téléphonie — pivot d'architecture post-Phase 12.

`pbx_connectors` était une ressource GLOBALE (un même PBX physique pouvant
héberger plusieurs tenants, rattachement via `pbx_domains_tenants`), gérée
par le super-admin global. Revu : chaque tenant possède et configure
désormais SON propre connecteur PBX (comme `SmtpSetting`/`ImapSetting`),
géré par son admin de tenant — `pbx_connectors` devient tenant-scopée
(`tenant_id` direct). `pbx_domains_tenants` est renommée
`pbx_connector_domains` et perd sa colonne `tenant_id` propre (héritée
implicitement du connecteur parent).

Ajout de 4 colonnes de suivi live sur `pbx_connectors` (rapportées par le
Core Connector — heartbeat + bouton "Sync") : `is_connected`,
`last_seen_at`, `last_error`, `sync_requested_at`.

Garde-fou données : `pbx_connectors` n'a été mergé (Phase 12) que le jour
même de cette migration — abandon plutôt que de deviner un `tenant_id` pour
un connecteur potentiellement partagé entre plusieurs tenants sous l'ancien
modèle. Les tables sont DROP puis recréées (plutôt qu'ALTER) uniquement
après confirmation qu'elles sont vides — aucune perte de données possible
si le garde-fou passe.

Revision ID: e7f8a9b0c1d2
Revises: d0e1f2a3b4c5
Create Date: 2026-07-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None

_JSONB_VARIANT = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade():
    bind = op.get_bind()
    existing = bind.execute(sa.text("SELECT id, name FROM pbx_connectors")).fetchall()
    if existing:
        offending = ", ".join(f"#{row[0]} ({row[1]})" for row in existing)
        raise RuntimeError(
            "Migration e7f8a9b0c1d2 : des pbx_connectors existent déjà "
            f"({offending}). Le passage au scoping tenant nécessite un "
            "tenant_id explicite qui ne peut pas être deviné automatiquement "
            "pour un connecteur potentiellement partagé entre plusieurs "
            "tenants sous l'ancien modèle. Réattribuer manuellement (ou "
            "supprimer) ces lignes puis relancer la migration."
        )

    # FK entrante (telephony_events.pbx_connector_id) à retirer avant de
    # pouvoir DROP la table, réajoutée en fin de migration.
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_telephony_events_pbx_connector', type_='foreignkey')

    op.drop_table('pbx_domains_tenants')
    op.drop_table('pbx_connectors')

    op.create_table(
        'pbx_connectors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_connected', sa.Boolean(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column('sync_requested_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('pbx_connectors', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pbx_connectors_tenant_id'), ['tenant_id'], unique=False)

    op.create_table(
        'pbx_connector_domains',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pbx_connector_id', sa.Integer(), nullable=False),
        sa.Column('pbx_domain', sa.String(length=255), nullable=False),
        sa.Column('queue_ids', _JSONB_VARIANT, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pbx_connector_id'], ['pbx_connectors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pbx_connector_id', 'pbx_domain', name='uq_pbx_domain_per_connector'),
    )
    with op.batch_alter_table('pbx_connector_domains', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pbx_connector_domains_pbx_connector_id'), ['pbx_connector_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_pbx_connector_domains_pbx_domain'), ['pbx_domain'], unique=False)

    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_telephony_events_pbx_connector', 'pbx_connectors',
            ['pbx_connector_id'], ['id'], ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_telephony_events_pbx_connector', type_='foreignkey')

    op.drop_table('pbx_connector_domains')
    op.drop_table('pbx_connectors')

    op.create_table(
        'pbx_connectors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'pbx_domains_tenants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pbx_connector_id', sa.Integer(), nullable=False),
        sa.Column('pbx_domain', sa.String(length=255), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('queue_ids', _JSONB_VARIANT, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['pbx_connector_id'], ['pbx_connectors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pbx_connector_id', 'pbx_domain', name='uq_pbx_domain_per_connector'),
    )
    with op.batch_alter_table('pbx_domains_tenants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pbx_domains_tenants_pbx_connector_id'), ['pbx_connector_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_pbx_domains_tenants_pbx_domain'), ['pbx_domain'], unique=False)
        batch_op.create_index(batch_op.f('ix_pbx_domains_tenants_tenant_id'), ['tenant_id'], unique=False)

    with op.batch_alter_table('telephony_events', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_telephony_events_pbx_connector', 'pbx_connectors',
            ['pbx_connector_id'], ['id'], ondelete='SET NULL',
        )
