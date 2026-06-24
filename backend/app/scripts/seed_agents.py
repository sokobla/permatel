"""
Seeding PERMATEL — Import d'agents de sécurité depuis Excel.

Lit le fichier Excel `lists_agents_secu.xlsx` et crée ou met à jour les
entités `AgentSecurite` (et leur `Contact` associé) pour le tenant cible.

Commande Flask associée (enregistrée dans app/__init__.py) :

  flask seed-agents --tenant-code <CODE> [options]

Options :
  --tenant-code      CODE    Tenant cible (obligatoire).
  --prestataire-code CODE    Code d'un prestataire ciblé (optionnel, sinon INTERNE).
  --file             PATH    Chemin vers le fichier Excel (défaut : chemin embarqué).
  --dry-run                  Simule sans écriture (défaut : activé).
  --no-dry-run               Applique les écritures.
  --verbose                  Affiche le détail de chaque enregistrement.
  --yes                      Bypass la confirmation interactive.

Arbitrages appliqués (validés par le métier) :
  1. Scission Nom/Prénom : Algorithme par virgule ou détection de casse mixte.
  2. Code postal        : Rangement dans le champ dédié `code_postal`.
  3. Qualification       : Attribution `type_agent = "Agent de sécurité"` par défaut
                           et conservation de l'intitulé d'origine dans `qualification`.
  4. Données externes    : Abandon des colonnes RH/Paie (Secteur, Entré le, Contrat, TX Mensuel).
  5. Prestataire         : Interne par défaut (`NULL`), surchargeable par `--prestataire-code`.
  6. Idempotence         : Recherche par (tenant_id, matricule) → CREATE ou UPDATE.
"""

import os
import re
from pathlib import Path

import click
import openpyxl
from flask import g
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.agent_securite import AgentSecurite
from app.models.contact import Contact
from app.models.prestataire import Prestataire
from app.models.tenant import Tenant
from app.routes.agents_securite import _sync_agent_contact

# ── Chemin par défaut vers le fichier source ─────────────────────────────────
_HERE = Path(__file__).resolve().parent          # app/scripts/
_DEFAULT_FILE = (
    _HERE.parent.parent / "resources" / "lists_agents_secu.xlsx"
)


# ─────────────────────────────────────────────────────────────────────────────
#  Utilitaires de normalisation et scission
# ─────────────────────────────────────────────────────────────────────────────

def _fix_str(value) -> str | None:
    """Retourne une chaîne nettoyée ou None si vide / None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _split_nom_prenom(full_name: str) -> tuple[str, str]:
    """Sépare le nom et le prénom selon la présence d'une virgule ou de mots en casse mixte."""
    s = full_name.strip()
    if ',' in s:
        parts = s.split(',', 1)
        return parts[0].strip(), parts[1].strip()
    
    # Sans virgule : recherche des mots en casse mixte (ex: Arounan) vs majuscules (ex: BAKAYOKO)
    words = s.split()
    nom_words = []
    prenom_words = []
    
    for w in words:
        if w.isupper():
            nom_words.append(w)
        else:
            prenom_words.append(w)
            
    if not nom_words and prenom_words:
        # Fallback si tout est en casse mixte
        nom_words.append(prenom_words.pop(0))
    elif not prenom_words and nom_words:
        # Fallback si tout est en majuscules
        prenom_words.append(nom_words.pop(-1))
        
    return " ".join(nom_words), " ".join(prenom_words)


def _clean_phone(value) -> str | None:
    """Nettoie le numéro de téléphone pour ne conserver que les chiffres."""
    if not value:
        return None
    s = str(value).strip()
    clean = "".join(c for c in s if c.isdigit())
    return clean if clean else None


def _clean_cp(value) -> str | None:
    """Normalise un code postal Excel (float ou str) en str à 5 chiffres."""
    if value is None:
        return None
    try:
        cp = str(int(float(value))).strip()
        return cp.zfill(5)
    except (ValueError, TypeError):
        return _fix_str(value)


# ─────────────────────────────────────────────────────────────────────────────
#  COMMANDE CLI
# ─────────────────────────────────────────────────────────────────────────────

@click.command("seed-agents")
@click.option("--tenant-code", required=True, help="Code du tenant cible.")
@click.option("--prestataire-code", default=None, help="Code optionnel d'un prestataire existant pour rattacher les agents.")
@click.option("--file", default=None, help="Chemin vers le fichier Excel (défaut : list_agents_secu.xlsx).")
@click.option("--dry-run/--no-dry-run", default=True, help="Simule sans écrire en base (défaut : activé).")
@click.option("--verbose", is_flag=True, help="Affiche le détail de chaque agent importé.")
@click.option("--yes", is_flag=True, help="Bypass la confirmation interactive.")
@with_appcontext
def seed_agents_command(tenant_code, prestataire_code, file, dry_run, verbose, yes):
    """Importe ou met à jour des agents de sécurité depuis un fichier Excel (idempotent)."""
    click.echo(
        "\n==============================================================\n"
        "  PERMATEL — Seeding Agents de Sécurité (Excel → Tenant)\n"
        "=============================================================="
    )

    if dry_run:
        click.echo("  [MODE DRY-RUN] Simulation active. Aucune modification en base.\n")
    else:
        click.echo("  [MODE REEL] Écriture en base activée.\n")

    # ── 1. Vérification du Tenant ────────────────────────────────────────────
    tenant = Tenant.query.filter_by(code=tenant_code, is_active=True).first()
    if not tenant:
        raise click.ClickException(f"Tenant '{tenant_code}' introuvable ou inactif en base.")
    
    # Assigne g.tenant pour garantir le bon fonctionnement de _sync_agent_contact
    g.tenant = tenant
    click.echo(f"  OK    Tenant identifié : {tenant.nom} ({tenant.code})")

    # ── 2. Vérification du Prestataire (optionnel) ───────────────────────────
    prestataire = None
    if prestataire_code:
        prestataire = Prestataire.query.filter_by(tenant_id=tenant.id, code_prestataire=prestataire_code).first()
        if not prestataire:
            raise click.ClickException(f"Prestataire '{prestataire_code}' introuvable pour le tenant '{tenant_code}'.")
        click.echo(f"  OK    Prestataire cible : {prestataire.nom} ({prestataire.code_prestataire})")
    else:
        click.echo("  OK    Rattachement    : INTERNE (prestataire_id = NULL)")

    # ── 3. Localisation du fichier ───────────────────────────────────────────
    file_path = Path(file) if file else _DEFAULT_FILE
    if not file_path.exists():
        raise click.ClickException(f"Fichier introuvable : {file_path}")
    
    click.echo(f"  OK    Fichier source  : {file_path.name}")

    if not dry_run and not yes:
        click.confirm("\nÊtes-vous sûr de vouloir appliquer cet import en base ?", abort=True)

    # ── 4. Lecture du fichier Excel ──────────────────────────────────────────
    click.echo("\n[PHASE 1] Lecture et parsing du fichier Excel...")
    
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active

    raw_rows = list(sheet.iter_rows(values_only=True))
    if len(raw_rows) < 4:
        raise click.ClickException("Le fichier semble vide ou ne respecte pas la structure attendue.")

    # Exclusion des lignes 1 à 3 (titre, sous-titre, en-têtes)
    data_rows = raw_rows[3:]

    # Map pour stocker les lignes valides
    agents_data = []
    ignored = 0

    for idx, row in enumerate(data_rows, start=4):
        # Sécurité : vérifier si c'est la ligne de total en bas
        first_val = _fix_str(row[0])
        if not first_val or first_val.lower().startswith("total"):
            ignored += 1
            continue

        # Extraction selon colonnes Excel (12 colonnes)
        # Nom/Prénom, Société, Secteur, Matricule, Entré le, Téléphone, C.P, Ville, Qualification, Contrat, TX Mensuel, TX Hor
        full_name  = first_val
        matricule  = _fix_str(row[3])
        telephone  = _clean_phone(row[5])
        cp         = _clean_cp(row[6])
        ville      = _fix_str(row[7])
        qualif     = _fix_str(row[8])
        tx_hor     = row[11]

        if not matricule:
            click.echo(f"  WARN  Ligne {idx} ignorée : Matricule manquant.", err=True)
            ignored += 1
            continue

        nom, prenom = _split_nom_prenom(full_name)

        agents_data.append({
            "matricule": matricule,
            "nom": nom,
            "prenom": prenom,
            "adresse": cp or "Non renseignée",  # Fallback adresse requis par Contact
            "ville": ville,
            "code_postal": cp,
            "telephone": telephone or "0600000000",  # Fallback si vide car requis par Contact
            "email": f"{matricule.lower()}@permatel.tmp",  # Fallback email requis par Contact
            "qualification": qualif,
            "taux_horaire": tx_hor if isinstance(tx_hor, (int, float)) else None,
            "type_agent": "Agent de sécurité",
            "motorise": False,
            "is_active": True,
            "prestataire_id": prestataire.id if prestataire else None,
        })

    click.echo(f"  OK    Lignes extraites : {len(agents_data)} (Ignorées : {ignored})")

    # ── 5. Phase de Seeding (CREATE / UPDATE) ────────────────────────────────
    click.echo("\n[PHASE 2] Synchronisation des Agents (Idempotence)...")

    counters = {"created": 0, "updated": 0, "rejected": 0}

    for a_data in agents_data:
        try:
            existing = AgentSecurite.query.filter_by(
                tenant_id=tenant.id,
                matricule=a_data["matricule"],
            ).first()

            if existing:
                # UPDATE
                existing.nom = a_data["nom"]
                existing.prenom = a_data["prenom"]
                existing.adresse = a_data["adresse"]
                existing.ville = a_data["ville"]
                existing.code_postal = a_data["code_postal"]
                existing.telephone = a_data["telephone"]
                existing.qualification = a_data["qualification"]
                if a_data["taux_horaire"] is not None:
                    existing.taux_horaire = a_data["taux_horaire"]
                existing.prestataire_id = a_data["prestataire_id"]
                existing.is_active = True

                # Synchronisation du contact
                _sync_agent_contact(existing, a_data)
                
                db.session.flush()
                counters["updated"] += 1
                action = "MAJ"
            else:
                # CREATE
                agent = AgentSecurite(
                    tenant_id=tenant.id,
                    matricule=a_data["matricule"],
                    nom=a_data["nom"],
                    prenom=a_data["prenom"],
                    adresse=a_data["adresse"],
                    ville=a_data["ville"],
                    code_postal=a_data["code_postal"],
                    telephone=a_data["telephone"],
                    email=a_data["email"],
                    qualification=a_data["qualification"],
                    taux_horaire=a_data["taux_horaire"],
                    type_agent=a_data["type_agent"],
                    motorise=a_data["motorise"],
                    is_active=a_data["is_active"],
                    prestataire_id=a_data["prestataire_id"],
                )
                _sync_agent_contact(agent, a_data)
                db.session.add(agent)
                db.session.flush()
                counters["created"] += 1
                action = "CREE"

            if verbose:
                click.echo(f"  {action:<5} Agent : {a_data['matricule']} | {a_data['nom']} {a_data['prenom']}")

        except IntegrityError as exc:
            db.session.rollback()
            counters["rejected"] += 1
            click.echo(f"  ERR   Agent '{a_data['matricule']}' rejeté : {exc.orig}", err=True)

    # ── 6. Bilan et Clôture ──────────────────────────────────────────────────
    if dry_run:
        db.session.rollback()
        click.echo("\n[BILAN DRY-RUN] Opérations simulées (rollback effectué) :")
    else:
        db.session.commit()
        click.echo("\n[BILAN REEL] Opérations validées en base :")

    click.echo(
        f"  - Agents créés      : {counters['created']}\n"
        f"  - Agents mis à jour : {counters['updated']}\n"
        f"  - Rejets / Erreurs  : {counters['rejected']}\n"
        "==============================================================\n"
    )
