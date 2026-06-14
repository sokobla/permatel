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
    # Cette logique s'exécute à chaque démarrage de l'application.
    # Elle est idempotente : elle crée la DB si elle n'existe pas, ou la met à jour si elle existe.
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table('alembic_version'):
            app.logger.info("Création de la base de données à partir de zéro...")
            db.create_all()
            stamp()  # Marque la base comme à jour avec les migrations
            app.logger.info("Insertion des données initiales (seeding)...")
            seeding.seed_full_tenant_and_users(db)
            app.logger.info("Initialisation de la base de données terminée.")
        else:
            app.logger.info("Base de données existante. Application des migrations et du seeding...")
            upgrade()
            seeding.seed_full_tenant_and_users(db)
            app.logger.info("Mise à jour de la base de données terminée.")
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
        """Initialise la base de données (crée ou met à jour le schéma) et insère les données de base."""
        inspector = inspect(db.engine)
        # alembic_version est la table que flask-migrate utilise pour suivre les migrations.
        # Si elle n'existe pas, la base est probablement vide.
        if not inspector.has_table('alembic_version'):
            click.echo("Création de la base de données à partir de zéro...")
            db.create_all()
            click.echo("Tables de la base de données créées.")
            
            click.echo("Marquage de la base de données avec la dernière version de migration...")
            stamp()
            
            click.echo("Insertion des données initiales (seeding)...")
            seeding.seed_full_tenant_and_users(db)
            click.echo("Données initiales insérées.")
        else:
            click.echo("La structure de la base de données existe déjà. Application des migrations...")
            upgrade()
            click.echo("Migrations appliquées.")
            
            click.echo("Vérification et insertion de nouvelles données de base (si nécessaire)...")
            seeding.seed_full_tenant_and_users(db)
            click.echo("Vérification des données de base terminée.")


    @click.command("seed-users")
    @with_appcontext
    def seed_users_command():
        """Insere les utilisateurs de test (admin, manager, permanencier) sans tenant."""
        seeding.seed_standalone_users(db)

    @click.command("seed")
    @with_appcontext
    def seed_command():
        """Crée le tenant par défaut et les utilisateurs associés."""
        seeding.seed_full_tenant_and_users(db)

    app.cli.add_command(init_db_command, "init-db")
    app.cli.add_command(seed_users_command, "seed-users")
    app.cli.add_command(seed_command, "seed")

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
