from datetime import timedelta
import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    DEBUG = False
    TESTING = False
    # Environnement d'exécution (piloté par .env : FLASK_ENV)
    FLASK_ENV = os.getenv("FLASK_ENV", "development").lower()
    # Applique automatiquement les migrations au démarrage si la base existe
    AUTO_MIGRATE = _as_bool(os.getenv("AUTO_MIGRATE"), default=True)
    PORT = int(os.getenv("PORT", 5000))
    VERSION = os.getenv("APP_VERSION", "1.0.0")
    BINDADDR = os.getenv("BINDADDR", "0.0.0.0")
    SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
    JWT_ALGORITHM = "HS256"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 1))
    )
    # Active la vérification blocklist dans le callback @jwt.token_in_blocklist_loader
    JWT_BLACKLIST_ENABLED = True
    # Clé de chiffrement des secrets applicatifs (mot de passe SMTP…).
    # À défaut, dérivée de JWT_SECRET_KEY. Définir une valeur dédiée en production.
    SETTINGS_ENCRYPTION_KEY = os.environ.get("SETTINGS_ENCRYPTION_KEY")
    # Adresse support de repli (si aucun tenant ne définit support_email)
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL")
    SESSION_INACTIVITY_TIMEOUT = int(
        os.environ.get("SESSION_INACTIVITY_TIMEOUT_MINUTES", 30)
    )
    # Anti-brute-force /auth/login (verrouillage temporaire)
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", 5))
    LOGIN_WINDOW_MINUTES = int(os.environ.get("LOGIN_WINDOW_MINUTES", 15))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", 15))
    # Backend partagé du compteur anti-brute-force (obligatoire en prod
    # multi-worker Gunicorn — sans Redis le seuil de verrouillage est dilué
    # par le nombre de workers). Repli sur un compteur en mémoire si absent.
    REDIS_URL = os.environ.get("REDIS_URL")
    # Jeton technique partagé attendu sur l'en-tête X-Connector-Token par
    # POST /api/telephony/events/ingest (le connecteur PBX n'est pas un
    # utilisateur PERMATEL, pas d'authentification JWT sur cet endpoint).
    TELEPHONY_CONNECTOR_TOKEN = os.environ.get("TELEPHONY_CONNECTOR_TOKEN")
    # Trace diagnostique du webhook CDR (POST /telephony/cdr/ingest/<token>) :
    # journalise l'inventaire complet des variables reçues + écrit le
    # payload intégral dans un fichier, pour valider quelles variables un
    # PBX réel envoie effectivement (cf. TELEPHONIE_INTEGRATION_PLAN.md).
    # Désactivé par défaut — un CDR complet peut peser plusieurs dizaines de
    # Ko, à activer ponctuellement le temps d'un appel de test.
    TELEPHONY_CDR_TRACE = os.environ.get("TELEPHONY_CDR_TRACE", "false").lower() == "true"
    # Mode async Flask-SocketIO. "threading" par défaut : évite qu'Engine.IO
    # importe (donc monkey-patche) eventlet au simple chargement de l'app —
    # utile en dev/tests (pytest, `flask run`) où rien n'a pré-patché le
    # process. En production, GUNICORN_WORKER_CLASS=eventlet fait tourner le
    # worker Gunicorn sous eventlet (patché avant l'import de l'app) : y
    # positionner SOCKETIO_ASYNC_MODE=eventlet dans l'environnement.
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "threading")

    # Base de données PostgreSQL
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'permatel')
    
    SQLALCHEMY_ECHO = True  # Log des requêtes SQL (désactiver en prod)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Utilise DATABASE_URL s'il est défini (priorité Docker), sinon construit à partir des composants
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
    # Tuning du pool de connexions (chaque worker Gunicorn a son propre pool) :
    # - pool_pre_ping : évite les "server closed the connection unexpectedly"
    #   sur une connexion coupée par un timeout firewall/NAT/Postgres.
    # - pool_recycle : recycle les connexions avant qu'elles ne soient fermées
    #   silencieusement côté serveur (doit rester < timeout réseau/Postgres).
    # - pool_size/max_overflow : borne le nombre de connexions par worker pour
    #   ne pas épuiser `max_connections` côté Postgres à mesure que le nombre
    #   de workers/tenants augmente.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE_SECONDS", 1800)),
        "pool_size": int(os.environ.get("DB_POOL_SIZE", 5)),
        "max_overflow": int(os.environ.get("DB_POOL_MAX_OVERFLOW", 10)),
        "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT_SECONDS", 30)),
    }
    
    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:8080').split(',')

    # URL publique du frontend (liens d'invitation d'onboarding).
    FRONTEND_BASE_URL = os.environ.get(
        'FRONTEND_BASE_URL',
        (CORS_ORIGINS[0].strip() if CORS_ORIGINS else 'http://localhost:8080'),
    )
    
    # Upload fichiers
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max
    
    # Timezone
    TIMEZONE = 'UTC'


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    PORT = int(os.getenv("PORT", 5000))
    # For testing: use in-memory SQLite database for isolation and portability
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # SQLite (SingletonThreadPool sur :memory:) n'accepte pas pool_size/
    # max_overflow/pool_timeout (options QueuePool, spécifiques à Postgres).
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SQLALCHEMY_ECHO = False
    TELEPHONY_CONNECTOR_TOKEN = "test-connector-token"



Config = DevelopmentConfig

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}