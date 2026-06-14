import click

from app.models.user import User, UserRole
from app.models.tenant import Tenant

USERS_SEED = [
    {
        "username": "admin",
        "email": "admin@permatel.ma",
        "password": "Admin123!",
        "nom": "Alaoui",
        "prenom": "Karim",
        "role": UserRole.ADMIN,
        "telephone": "+212600000001",
        "agent_login": None,
        "station_extension": None,
        "is_active": True,
    },
    {
        "username": "manager",
        "email": "manager@permatel.ma",
        "password": "Manager123!",
        "nom": "Benali",
        "prenom": "Sara",
        "role": UserRole.MANAGER,
        "telephone": "+212600000002",
        "agent_login": None,
        "station_extension": None,
        "is_active": True,
    },
    {
        "username": "permanencier",
        "email": "permanencier@permatel.ma",
        "password": "Perm123!",
        "nom": "Idrissi",
        "prenom": "Youssef",
        "role": UserRole.PERMANENCIER,
        "telephone": "+212600000003",
        "agent_login": "yidrissi",
        "station_extension": "101",
        "is_active": True,
    },
]

SEED_TENANT = {
    "code": "ADM-SEC",
    "nom": "ADM Sécurité",
    "slug": "adm-securite",
}

SEED_USERS_FULL = [
    {
        "username": "adm_admin",
        "email": "adm.admin@permatel.ma",
        "password": "Admin123!",
        "nom": "Alaoui",
        "prenom": "Karim",
        "role": UserRole.ADMIN,
        "telephone": "+212610000001",
        "agent_login": None,
        "station_extension": None,
        "is_active": True,
    },
    {
        "username": "adm_manager",
        "email": "adm.manager@permatel.ma",
        "password": "Manager123!",
        "nom": "Benali",
        "prenom": "Sara",
        "role": UserRole.MANAGER,
        "telephone": "+212610000002",
        "agent_login": None,
        "station_extension": None,
        "is_active": True,
    },
    {
        "username": "adm_perm",
        "email": "adm.perm@permatel.ma",
        "password": "Perm123!",
        "nom": "Idrissi",
        "prenom": "Youssef",
        "role": UserRole.PERMANENCIER,
        "telephone": "+212610000003",
        "agent_login": "yidrissi",
        "station_extension": "201",
        "is_active": True,
    },
]


def seed_standalone_users(db):
    """Insere les utilisateurs de test (admin, manager, permanencier) sans tenant."""
    click.echo("=" * 55)
    click.echo("  PERMATEL -- Seed utilisateurs (sans tenant)")
    click.echo("=" * 55)
    created = 0
    skipped = 0
    for data in USERS_SEED:
        existing = User.query.filter_by(username=data["username"]).first()
        if existing:
            click.echo(
                f"  --  {data['username']:<15} [{data['role'].value}]"
                f"  -> deja existant, ignore"
            )
            skipped += 1
            continue
        user = User(**{k: v for k, v in data.items() if k != "password"})
        user.set_password(data["password"])
        db.session.add(user)
        click.echo(
            f"  OK  {data['username']:<15} [{data['role'].value}]"
            f"  -> cree (mdp: {data['password']})"
        )
        created += 1
    db.session.commit()
    click.echo("=" * 55)
    click.echo(f"  Resultat : {created} cree(s), {skipped} ignore(s)")
    click.echo("=" * 55)


def seed_full_tenant_and_users(db):
    from sqlalchemy.exc import ProgrammingError
    """
    Cree le tenant 'ADM Securite' et 3 comptes (ADMIN, MANAGER, PERMANENCIER).
    Chaque compte est lie au tenant. Idempotent : ne cree pas de doublon.
    """
    click.echo("=" * 60)
    click.echo("  PERMATEL -- Seed complet (tenant + utilisateurs)")
    click.echo("=" * 60)
    try:
        tenant = Tenant.query.filter_by(code=SEED_TENANT["code"]).first()
        if tenant:
            click.echo(
                f"  --  Tenant '{SEED_TENANT['nom']}' ({SEED_TENANT['code']})"
                f"  -> deja existant, reutilise"
            )
        else:
            tenant = Tenant(**SEED_TENANT, is_active=True)
            db.session.add(tenant)
            db.session.flush()
            click.echo(
                f"  OK  Tenant '{SEED_TENANT['nom']}' ({SEED_TENANT['code']})"
                f"  -> cree (id={tenant.id})"
            )
        created = 0
        skipped = 0
        for data in SEED_USERS_FULL:
            existing = User.query.filter_by(username=data["username"]).first()
            if existing:
                if tenant not in existing.tenants:
                    existing.tenants.append(tenant)
                    click.echo(
                        f"  --  {data['username']:<15} [{data['role'].value}]"
                        f"  -> existant, tenant ajoute"
                    )
                else:
                    click.echo(
                        f"  --  {data['username']:<15} [{data['role'].value}]"
                        f"  -> deja existant et lie, ignore"
                    )
                skipped += 1
                continue
            user = User(**{k: v for k, v in data.items() if k != "password"})
            user.set_password(data["password"])
            user.tenants.append(tenant)
            db.session.add(user)
            click.echo(
                f"  OK  {data['username']:<15} [{data['role'].value}]"
                f"  -> cree et lie au tenant (mdp: {data['password']})"
            )
            created += 1
        db.session.commit()
        click.echo("=" * 60)
        click.echo(f"  Resultat : {created} cree(s), {skipped} ignore(s)")
        click.echo("")
        click.echo("  Comptes disponibles :")
        click.echo(f"    adm_admin   / Admin123!    [ADMIN]")
        click.echo(f"    adm_manager / Manager123!  [MANAGER]")
        click.echo(f"    adm_perm    / Perm123!     [PERMANENCIER]")
        click.echo(f"  Tenant : ADM Securite ({SEED_TENANT['code']})")
        click.echo("=" * 60)
    except ProgrammingError as e:
        db.session.rollback()
        click.secho(
            "\n  AVERTISSEMENT: Impossible d'exécuter le seeding. La base de données n'est probablement pas à jour.",
            fg="yellow",
        )
        click.echo(f"  Erreur: {e.orig}")
        click.echo("  -> Exécutez 'flask db upgrade' et réessayez.\n")
        return