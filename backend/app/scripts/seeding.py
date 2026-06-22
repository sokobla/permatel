"""
Seeding PERMATEL — amorce unique.

Une seule amorce est configurée : un tenant « Root » et un utilisateur
administrateur global. Aucune donnée de démonstration, aucune fixture.

  flask seed     -> (ré)amorce Root + admin global (idempotent)
  flask init-db  -> crée le schéma si besoin puis amorce Root + admin

Le helper `seed_reference_values` reste disponible : il est appelé à la
création d'un tenant (route POST /api/tenants) pour pré-remplir ses valeurs de
référence par défaut. Il ne fait pas partie de l'amorce de démarrage.
"""
import click


# ─────────────────────────────────────────────────────────────────────────────
#  Amorce unique : tenant Root + administrateur global
# ─────────────────────────────────────────────────────────────────────────────
ROOT_TENANT = {"code": "ROOT", "nom": "Root", "slug": "root"}
ROOT_ADMIN = {
    # username = email (bascule globale de l'identifiant)
    "username": "adm_root@permatel.local",
    "email": "adm_root@permatel.local",
    "password": "admin123!",
    "nom": "Root",
    "prenom": "Admin",
}


def seed_root(db) -> dict:
    """
    Amorce minimale et idempotente :
      - 1 tenant « Root » (code ROOT) ;
      - 1 administrateur global (role ADMIN) username/email adm_root@permatel.local.

    L'admin global accède à tous les tenants : aucune appartenance n'est créée.
    Relance sans effet si les entités existent déjà.
    """
    from app.models.tenant import Tenant
    from app.models.user import User, UserRole

    click.echo("=" * 60)
    click.echo("  PERMATEL -- Amorce unique (tenant Root + admin global)")
    click.echo("=" * 60)

    result = {"tenant_created": False, "admin_created": False}

    tenant = Tenant.query.filter_by(code=ROOT_TENANT["code"]).first()
    if tenant:
        click.echo(f"  --  Tenant '{ROOT_TENANT['nom']}' déjà présent.")
    else:
        tenant = Tenant(**ROOT_TENANT, is_active=True)
        db.session.add(tenant)
        db.session.flush()
        result["tenant_created"] = True
        click.echo(f"  OK  Tenant '{ROOT_TENANT['nom']}' créé (id={tenant.id}).")

    admin = User.query.filter_by(username=ROOT_ADMIN["username"]).first()
    if admin:
        click.echo(f"  --  Admin '{ROOT_ADMIN['username']}' déjà présent.")
    else:
        admin = User(
            username=ROOT_ADMIN["username"],
            email=ROOT_ADMIN["email"],
            nom=ROOT_ADMIN["nom"],
            prenom=ROOT_ADMIN["prenom"],
            role=UserRole.ADMIN,
            is_active=True,
        )
        admin.set_password(ROOT_ADMIN["password"])
        db.session.add(admin)
        db.session.flush()
        result["admin_created"] = True
        click.echo(f"  OK  Admin global '{ROOT_ADMIN['username']}' créé.")

    db.session.commit()
    click.echo("-" * 60)
    click.echo(f"  Connexion : {ROOT_ADMIN['username']} / {ROOT_ADMIN['password']}")
    click.echo("  Pensez à changer le mot de passe après la première connexion.")
    click.echo("=" * 60)
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Valeurs de référence par défaut (par tenant) — utilisé à la création de tenant
# ─────────────────────────────────────────────────────────────────────────────
# Chaque entrée = (code, label). `code` est None pour les familles à libellés
# libres ; il vaut la clé d'enum backend pour les familles couplées à la logique.
DEFAULT_REFERENCE_VALUES = {
    "nature_anomalie": [
        ("anj", "Absence non justifiée (ANJ)"), ("absence_justifiee", "Absence justifiée"),
        ("retard_prise_service", "Retard prise de service"), ("agent_non_sur_site", "Agent non sur site"),
        ("doublon_planning", "Doublon planning"), ("remplacement_permutation", "Remplacement / permutation"),
        ("modification_vacation", "Modification vacation"), ("probleme_technique", "Problème technique"),
        ("site_prestataire_injoignable", "Site / prestataire injoignable"), ("blocage_outil_rh", "Blocage outil / RH"),
        ("demande_de_renfort", "Demande de renfort"), ("anomalie_facturation", "Anomalie facturation"),
        ("autre", "Autre"),
    ],
    "statut_demande": [
        ("nouvelle", "Nouvelle"), ("en_cours", "En cours"), ("en_attente", "En attente"),
        ("resolue", "Résolue"), ("cloturee", "Clôturée"), ("annulee", "Annulée"),
    ],
    "type_mission": [
        ("gardiennage", "Gardiennage"), ("surveillance_mobile", "Surveillance mobile"),
        ("rondes", "Rondes"), ("intervention", "Intervention"), ("filtrage", "Filtrage"),
        ("protection_rapprochee", "Protection rapprochée"), ("accueil_securite", "Accueil sécurité"),
        ("autre", "Autre"),
    ],
    # Familles à libellés libres (code = None) : la valeur stockée est le libellé.
    "moyens_acces": [(None, x) for x in ["Clé", "Digicode", "Badge magnétique", "Interphone", "Accès libre", "Autre"]],
    "risques_specifiques": [(None, x) for x in ["Vol", "Intrusion", "Incendie", "Vandalisme", "Conflit social", "Risque terroriste"]],
    "besoins_agents": [(None, x) for x in ["Tenue fournie", "Formation SSIAP", "Habilitation électrique", "Maîtrise anglais", "Permis B", "Agent APS qualifié", "Autre"]],
}


def seed_reference_values(db, tenant_id) -> int:
    """
    Insère les valeurs de référence par défaut manquantes pour un tenant et
    complète les `code` absents sur les valeurs existantes. Idempotent.
    """
    from app.models.setting import ReferenceValue

    created = 0
    for family, entries in DEFAULT_REFERENCE_VALUES.items():
        existing = {
            r.label: r for r in ReferenceValue.query.filter_by(
                tenant_id=tenant_id, family=family
            ).all()
        }
        for pos, (code, label) in enumerate(entries):
            if label in existing:
                row = existing[label]
                if code and not row.code:  # backfill du code manquant
                    row.code = code
                continue
            db.session.add(ReferenceValue(
                tenant_id=tenant_id, family=family, label=label,
                code=code, position=pos, is_active=True,
            ))
            created += 1
    db.session.flush()
    return created
