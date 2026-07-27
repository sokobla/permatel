"""pbx_connectors_and_domains

Module Téléphonie — Phase 11 (fondations backend), tâche 11.2.

Crée les tables `pbx_connectors` (ressource GLOBALE, non tenant-scopée : un
même PBX physique peut héberger plusieurs tenants PERMATEL — CRUD réservé au
super-admin global) et `pbx_domains_tenants` (rattachement tenant-scopé d'un
domaine PBX à un tenant, avec les files d'attente supervisées).

`pbx_connectors.type` est un `String`, pas un enum Postgres, pour accueillir
un futur type de PBX (TSAPI) sans migration de schéma.

Revision ID: c9d0e1f2a3b4
Revises: b4d8e1f3a5c9
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c9d0e1f2a3b4'
down_revision = 'b4d8e1f3a5c9'
branch_labels = None
depends_on = None

# JSONB en PostgreSQL, repli JSON générique sous SQLite (tests) — même motif
# que JSONB_VARIANT dans app/models/demande.py.
_JSONB_VARIANT = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade():
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


def downgrade():
    with op.batch_alter_table('pbx_domains_tenants', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pbx_domains_tenants_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_pbx_domains_tenants_pbx_domain'))
        batch_op.drop_index(batch_op.f('ix_pbx_domains_tenants_pbx_connector_id'))
    op.drop_table('pbx_domains_tenants')
    op.drop_table('pbx_connectors')
