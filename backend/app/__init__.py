# third-party imports
import os
import click
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask.cli import with_appcontext

# local imports
from flask import Flask

from .config import BaseConfig, DevelopmentConfig, ProductionConfig, TestingConfig

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()

def create_app(config_object=None):
    if config_object is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()
        config_mapping = {
            "development": DevelopmentConfig,
            "production": ProductionConfig,
            "testing": TestingConfig,
            "default": DevelopmentConfig,
        }
        config_object = config_mapping.get(config_name, DevelopmentConfig)
    elif isinstance(config_object, str):
        config_mapping = {
            "development": DevelopmentConfig,
            "production": ProductionConfig,
            "testing": TestingConfig,
        }
        config_object = config_mapping.get(config_object.lower(), DevelopmentConfig)

    app = Flask(__name__)
    app.config.from_object(config_object)

    # Initialize extensions here, e.g. db.init_app(app), migrate.init_app(app, db)
    # Initialiser les extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config.get('CORS_ORIGINS', ["*"]), supports_credentials=True)

    Migrate(app, db)
    from app import models  # Importer les modeles pour que Flask-Migrate puisse les detecter
    from .models.token_blocklist import TokenBlocklist

    # Creer le dossier uploads s'il n'existe pas
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Enregistrer les commandes CLI
    from flask_migrate import upgrade, stamp
    from sqlalchemy import inspect
    # L'import de 'seeding' est déplacé ici pour être accessible par l'initialisation auto
    try:
        from .scripts import seeding
    except ImportError:
        # Fallback si la structure a changé pour app/seeding.py
        from . import seeding

    # --- Initialisation automatique de la base de données au démarrage ---
    # - Base vide (1er démarrage) : création du schéma + amorce unique (Root + admin global).
    # - Base existante : application des migrations en attente (si AUTO_MIGRATE).
    with app.app_context():
        inspector = inspect(db.engine)
        db_is_empty = not inspector.has_table('alembic_version')

        if db_is_empty:
            app.logger.info("Base vide — création du schéma à partir des modèles...")
            db.create_all()
            stamp(revision='heads')  # Marque la base comme à jour avec les migrations
            app.logger.info("Premier démarrage — amorce unique (tenant Root + admin global)...")
            seeding.seed_root(db)
            app.logger.info("Initialisation de la base de données terminée.")
        else:
            if app.config.get("AUTO_MIGRATE"):
                app.logger.info("Base existante — application des migrations en attente...")
                upgrade(revision='heads')
            else:
                app.logger.info("Base existante — migrations automatiques désactivées.")
    # --- Fin de l'initialisation automatique ---

    # Route pour servir les fichiers uploadés (avatars, etc.)
    # NOTE: Cette configuration est adaptée pour le développement.
    # En production, il est fortement recommandé de configurer votre serveur web
    # (Nginx, Apache...) pour servir ce dossier directement pour de meilleures performances.
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        from flask import send_from_directory
        
        # On utilise current_app pour accéder à la configuration de l'application
        upload_dir = app.config.get('UPLOAD_FOLDER')
        
        if not upload_dir:
            app.logger.error("La variable de configuration UPLOAD_FOLDER est manquante.")
            # Ne pas exposer les détails de la configuration à l'utilisateur
            return "Erreur de configuration du serveur.", 500
            
        return send_from_directory(upload_dir, filename)

    @click.command("init-db")
    @with_appcontext
    def init_db_command():
        """Crée le schéma si la base est vide, puis amorce Root + admin global."""
        inspector = inspect(db.engine)
        if not inspector.has_table('alembic_version'):
            click.echo("Création de la base de données à partir de zéro...")
            db.create_all()
            stamp()
            click.echo("Schéma créé.")
            seeding.seed_root(db)
        else:
            click.echo("La structure de la base existe déjà. Application des migrations...")
            upgrade(revision='heads')
            click.echo("Migrations appliquées.")

    @click.command("seed")
    @with_appcontext
    def seed_command():
        """Amorce unique : tenant Root + administrateur global (idempotent)."""
        seeding.seed_root(db)

    @click.command("sessions-sweep")
    @with_appcontext
    def sessions_sweep_command():
        """Expire les sessions inactives et purge la blocklist des tokens expirés."""
        from app.scripts.session_maintenance import sweep_sessions
        result = sweep_sessions(db)
        click.echo(
            f"Sessions expirées : {result['expired']} | "
            f"Entrées blocklist purgées : {result['purged']}"
        )

    @click.command("sla-backfill")
    @with_appcontext
    def sla_backfill_command():
        """Amorce les politiques SLA par défaut des tenants existants + recalcule les demandes actives."""
        from app.services.sla import backfill_all
        r = backfill_all(db)
        click.echo(
            f"Tenants : {r['tenants']} | politiques créées : {r['policies_created']} | "
            f"demandes recalculées : {r['demandes_recomputed']}"
        )

    @click.command("sla-sweep")
    @with_appcontext
    def sla_sweep_command():
        """Émet les alertes SLA (à risque / dépassé) pour les demandes ouvertes."""
        from app.services.sla import sla_sweep
        r = sla_sweep(db)
        click.echo(f"Alertes SLA — à risque : {r['warnings']} | dépassements : {r['breaches']}")

    @click.command("notifications-dispatch")
    @with_appcontext
    def notifications_dispatch_command():
        """Envoie les emails de notification en file (via le SMTP du tenant)."""
        from app.services.notifications import dispatch_emails
        r = dispatch_emails(db)
        click.echo(f"Emails — envoyés : {r['sent']} | échecs : {r['failed']}")

    @click.command("reencrypt-secrets")
    @click.argument("old_key")
    @with_appcontext
    def reencrypt_secrets_command(old_key):
        """Re-chiffre les données (ancienne clé -> SETTINGS_ENCRYPTION_KEY courante).

        Lancer APRÈS avoir mis la nouvelle clé en place : flask reencrypt-secrets <ancienne_cle>
        """
        from app.services.reencrypt import reencrypt_all
        r = reencrypt_all(db, old_key)
        click.echo(
            f"Re-chiffrement — SMTP : {r['smtp']} | IMAP : {r['imap']} | "
            f"emails : {r['emails']} | pièces jointes : {r['attachments']}"
        )

    @click.command("mail-fetch")
    @with_appcontext
    def mail_fetch_command():
        """Relève les emails entrants (IMAP) des tenants à réception activée."""
        from app.scripts.mail_fetch import fetch_all
        summary = fetch_all(db)
        if not summary:
            click.echo("Aucun tenant avec réception IMAP activée.")
        for code, n in summary.items():
            click.echo(f"  {code} : {n}")

    @click.command("backfill-qualifications")
    @with_appcontext
    def backfill_qualifications_command():
        """Injecte la famille 'qualification_agent' dans les tenants existants (idempotent)."""
        from app.models.tenant import Tenant
        tenants = Tenant.query.filter_by(is_active=True).all()
        total = 0
        for t in tenants:
            created = seeding.seed_reference_values(db, t.id)
            if created:
                click.echo(f"  OK  Tenant '{t.code}' : {created} valeur(s) ajoutée(s).")
            else:
                click.echo(f"  --  Tenant '{t.code}' : déjà à jour.")
            total += created
        db.session.commit()
        click.echo(f"Backfill terminé. Total : {total} valeur(s) insérée(s).")

    app.cli.add_command(init_db_command, "init-db")
    app.cli.add_command(seed_command, "seed")
    app.cli.add_command(sessions_sweep_command, "sessions-sweep")
    app.cli.add_command(sla_backfill_command, "sla-backfill")
    app.cli.add_command(sla_sweep_command, "sla-sweep")
    app.cli.add_command(notifications_dispatch_command, "notifications-dispatch")
    app.cli.add_command(reencrypt_secrets_command, "reencrypt-secrets")
    app.cli.add_command(mail_fetch_command, "mail-fetch")
    app.cli.add_command(backfill_qualifications_command, "backfill-qualifications")

    from app.scripts.seed_prestataires import seed_prestataires_command
    app.cli.add_command(seed_prestataires_command, "seed-prestataires")

    from app.scripts.superadmin_cli import superadmin_cli
    app.cli.add_command(superadmin_cli)

    # enregistrer les blueprints
    from app.routes.tenants import tenants_bp
    app.register_blueprint(tenants_bp)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.users import users_bp
    app.register_blueprint(users_bp)

    from app.routes.clients import clients_bp
    app.register_blueprint(clients_bp)

    from app.routes.sites import sites_bp
    app.register_blueprint(sites_bp)

    from app.routes.contacts import contacts_bp
    app.register_blueprint(contacts_bp)

    from app.routes.demandes import demandes_bp
    app.register_blueprint(demandes_bp)

    from app.routes.prestataires import prestataires_bp
    app.register_blueprint(prestataires_bp)
    
    from app.routes.agents_securite import agents_securite_bp
    app.register_blueprint(agents_securite_bp)

    from app.routes.interactions import interactions_bp
    app.register_blueprint(interactions_bp)

    from app.routes.settings import settings_bp
    app.register_blueprint(settings_bp)

    from app.routes.emails import emails_bp
    app.register_blueprint(emails_bp)

    from app.routes.support import support_bp
    app.register_blueprint(support_bp)

    from app.routes.tenant_members import tenant_members_bp
    app.register_blueprint(tenant_members_bp)

    from app.routes.invitations import invitations_bp
    app.register_blueprint(invitations_bp)

    from app.routes.notifications import notifications_bp
    app.register_blueprint(notifications_bp)

    from app.routes.prises_de_service import prises_de_service_bp
    app.register_blueprint(prises_de_service_bp)



    # ── Gestionnaires d'erreurs globaux (sécurité : pas de fuite de stack trace) ──
    # Transforme les erreurs SQL d'entrée (ex. valeur trop longue → 22001) en 400
    # propres au lieu de 500 verbeux, et masque toute exception inattendue.
    from sqlalchemy.exc import DataError, IntegrityError
    from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

    @app.errorhandler(DataError)
    def _handle_data_error(err):
        db.session.rollback()
        app.logger.warning(f"DataError: {getattr(err, 'orig', err)}")
        return {"error": "Données invalides ou trop volumineuses."}, 400

    @app.errorhandler(IntegrityError)
    def _handle_integrity_error(err):
        db.session.rollback()
        app.logger.warning(f"IntegrityError: {getattr(err, 'orig', err)}")
        return {"error": "Conflit de données : une contrainte n'est pas respectée."}, 409

    @app.errorhandler(RequestEntityTooLarge)
    def _handle_too_large(err):
        return {"error": "Charge utile trop volumineuse."}, 413

    @app.errorhandler(Exception)
    def _handle_unexpected(err):
        # Laisse passer les erreurs HTTP normales (401/403/404/400…)
        if isinstance(err, HTTPException):
            return err
        db.session.rollback()
        app.logger.exception("Exception non gérée")
        return {"error": "Une erreur interne est survenue."}, 500

    # Cabler la verification de blocklist (appelee automatiquement par Flask-JWT)
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return TokenBlocklist.query.filter_by(
            jti=jwt_payload["jti"]
        ).first() is not None

    @app.route("/health")
    def health():
        return {
            "status": "ok",
            "environment": app.config.get("FLASK_ENV", "development"),
            "version": app.config.get("APP_NAME", "") + " - " + app.config.get("VERSION", "unknown"),
            "debug": app.config.get("DEBUG", False),
        }

    return app
