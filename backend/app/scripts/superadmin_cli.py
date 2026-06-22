"""
CLI de gestion des super-admins globaux (role ADMIN).

Le rôle ADMIN = accès à TOUS les tenants. Il n'est volontairement pas gérable
via l'API /users ni l'interface : uniquement ici.

  flask superadmin list
  flask superadmin create  --email a@b.com --nom Doe --prenom John
  flask superadmin promote a@b.com
  flask superadmin demote  a@b.com [--to MANAGER]
  flask superadmin reset-password a@b.com
  flask superadmin disable a@b.com
  flask superadmin enable  a@b.com
"""
import click
from flask.cli import with_appcontext

from app import db
from app.models.user import User, UserRole
from app.models.tenant_user import TenantUser
from app.utils.validators import password_error


def _find(email):
    return User.query.filter(User.email.ilike(email.strip().lower())).first()


def _active_superadmin_count(exclude_id=None):
    q = User.query.filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.count()


@click.group("superadmin")
def superadmin_cli():
    """Gestion des super-admins globaux (role ADMIN)."""


@superadmin_cli.command("list")
@with_appcontext
def list_cmd():
    """Liste les super-admins globaux."""
    admins = User.query.filter_by(role=UserRole.ADMIN).order_by(User.id).all()
    if not admins:
        click.echo("Aucun super-admin.")
        return
    click.echo(f"{'ID':>4}  {'EMAIL':<35} {'ACTIF':<6} NOM")
    for u in admins:
        click.echo(f"{u.id:>4}  {u.email:<35} {'oui' if u.is_active else 'non':<6} {u.prenom} {u.nom}")


@superadmin_cli.command("create")
@click.option("--email", required=True)
@click.option("--nom", required=True)
@click.option("--prenom", required=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def create_cmd(email, nom, prenom, password):
    """Crée un nouveau super-admin global (username = email)."""
    email = email.strip().lower()
    pwd_err = password_error(password)
    if pwd_err:
        raise click.ClickException(pwd_err)
    if _find(email):
        raise click.ClickException(f"Un utilisateur existe déjà avec l'email {email}.")
    user = User(username=email, email=email, nom=nom.strip(), prenom=prenom.strip(),
                role=UserRole.ADMIN, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.secho(f"OK — super-admin créé : {email} (id={user.id}).", fg="green")


@superadmin_cli.command("promote")
@click.argument("email")
@with_appcontext
def promote_cmd(email):
    """Promeut un utilisateur existant en super-admin global."""
    user = _find(email)
    if not user:
        raise click.ClickException(f"Utilisateur introuvable : {email}.")
    if user.role == UserRole.ADMIN:
        click.echo("Déjà super-admin.")
        return
    user.role = UserRole.ADMIN
    db.session.commit()
    click.secho(f"OK — {user.email} est désormais super-admin global.", fg="green")


@superadmin_cli.command("demote")
@click.argument("email")
@click.option("--to", "to_role", default="MANAGER", show_default=True,
              type=click.Choice(["MANAGER", "PERMANENCIER"]))
@with_appcontext
def demote_cmd(email, to_role):
    """Rétrograde un super-admin vers un rôle standard (MANAGER/PERMANENCIER)."""
    user = _find(email)
    if not user:
        raise click.ClickException(f"Utilisateur introuvable : {email}.")
    if user.role != UserRole.ADMIN:
        click.echo("Cet utilisateur n'est pas super-admin.")
        return
    if _active_superadmin_count(exclude_id=user.id) == 0:
        raise click.ClickException("Refus : ce compte est le dernier super-admin actif.")
    user.role = UserRole(to_role)
    db.session.commit()
    click.secho(f"OK — {user.email} rétrogradé en {to_role}.", fg="green")
    if not TenantUser.query.filter_by(user_id=user.id, is_active=True).first():
        click.secho("  ⚠ Ce compte n'a aucune appartenance active : il ne pourra pas "
                    "se connecter tant qu'il n'est pas rattaché à un tenant.", fg="yellow")


@superadmin_cli.command("reset-password")
@click.argument("email")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@with_appcontext
def reset_password_cmd(email, password):
    """Réinitialise le mot de passe d'un super-admin."""
    user = _find(email)
    if not user or user.role != UserRole.ADMIN:
        raise click.ClickException(f"Super-admin introuvable : {email}.")
    pwd_err = password_error(password)
    if pwd_err:
        raise click.ClickException(pwd_err)
    user.set_password(password)
    db.session.commit()
    click.secho(f"OK — mot de passe réinitialisé pour {user.email}.", fg="green")


@superadmin_cli.command("disable")
@click.argument("email")
@with_appcontext
def disable_cmd(email):
    """Désactive un compte super-admin."""
    user = _find(email)
    if not user or user.role != UserRole.ADMIN:
        raise click.ClickException(f"Super-admin introuvable : {email}.")
    if user.is_active and _active_superadmin_count(exclude_id=user.id) == 0:
        raise click.ClickException("Refus : ce compte est le dernier super-admin actif.")
    user.is_active = False
    db.session.commit()
    click.secho(f"OK — {user.email} désactivé.", fg="green")


@superadmin_cli.command("enable")
@click.argument("email")
@with_appcontext
def enable_cmd(email):
    """Réactive un compte super-admin."""
    user = _find(email)
    if not user or user.role != UserRole.ADMIN:
        raise click.ClickException(f"Super-admin introuvable : {email}.")
    user.is_active = True
    db.session.commit()
    click.secho(f"OK — {user.email} réactivé.", fg="green")
