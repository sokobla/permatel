"""
Backfill initial ERP (Phase 6, ODOO_INTEGRATION_PLAN.md §2.6).

Commande Flask associée (enregistrée dans app/__init__.py) :

  flask erp-backfill --tenant-code <CODE> [options]

Options :
  --tenant-code   CODE    Tenant cible (obligatoire).
  --dry-run               Simule sans écriture (défaut : activé).
  --no-dry-run            Applique (Phase 6 : n'écrit encore rien, voir note).
  --yes                   Bypass la confirmation interactive.

⚠️ Squelette fonctionnel, pas encore de synchro réelle : cette commande
sert à amorcer l'écran (compter ce qui serait à synchroniser) mais aucune
table de mapping (`erp_partners`/`erp_employees`, §3.B) n'existe avant la
Phase 7 — sans elle, il n'y a rien de fiable à écrire côté ERP (on ne
saurait pas distinguer "déjà synchronisé" de "jamais tenté"). Le compte
rapporté est donc un simple "total éligible" (clients/sites/contacts/
agents actifs du tenant), avec un message explicite renvoyant à la Phase 7
pour la synchro réelle — même conventions CLI que `seed-prestataires`/
`seed-agents` (dry-run par défaut, --tenant-code, --yes) pour que la
commande définitive n'ait qu'à remplacer le corps du traitement.
"""
import click
from flask.cli import with_appcontext

from app.models.tenant import Tenant
from app.models.client import Client
from app.models.site import Site
from app.models.contact import Contact
from app.models.agent_securite import AgentSecurite


def _resolve_tenant(tenant_code):
    tenant = Tenant.query.filter_by(code=tenant_code).first()
    if not tenant:
        raise click.ClickException(f"Tenant '{tenant_code}' introuvable en base.")
    if not tenant.is_active:
        raise click.ClickException(f"Tenant '{tenant_code}' inactif.")
    return tenant


@click.command("erp-backfill")
@click.option(
    "--tenant-code", required=True,
    help="Code du tenant cible. Obligatoire.",
)
@click.option(
    "--dry-run/--no-dry-run", default=True, show_default=True,
    help="Simule sans écriture (défaut : activé).",
)
@click.option(
    "--yes", is_flag=True, default=False,
    help="Bypass la confirmation interactive (mode CI/CD).",
)
@with_appcontext
def erp_backfill_command(tenant_code, dry_run, yes):
    """Amorçage initial de la synchro ERP pour un tenant (squelette, cf. docstring module)."""
    tenant = _resolve_tenant(tenant_code)

    if not tenant.channel_erp:
        raise click.ClickException(
            f"Le canal ERP (integrations.erp) n'est pas activé pour le tenant '{tenant_code}'."
        )

    counts = {
        "clients": Client.query.filter_by(tenant_id=tenant.id).count(),
        "sites": Site.query.filter_by(tenant_id=tenant.id).count(),
        "contacts": (
            Contact.query.join(Contact.clients)
            .filter(Client.tenant_id == tenant.id).distinct().count()
        ),
        "agents": AgentSecurite.query.filter_by(tenant_id=tenant.id).count(),
    }
    total = sum(counts.values())

    click.echo(f"Tenant '{tenant_code}' — éligibles au backfill ERP :")
    for label, n in counts.items():
        click.echo(f"  {label:10s} : {n}")
    click.echo(f"  {'total':10s} : {total}")

    if dry_run:
        click.echo("\n[dry-run] Aucune écriture effectuée.")
        return

    if not yes:
        click.confirm(
            f"\nConfirmer le backfill ERP de {total} enregistrement(s) pour '{tenant_code}' ?",
            abort=True,
        )

    click.echo(
        "\nSynchronisation réelle non implémentée à ce stade (Phase 6 = "
        "fondations transverses) — disponible à partir de la Phase 7, une "
        "fois erp_partners/erp_employees en place (ODOO_INTEGRATION_PLAN.md §3.B)."
    )
