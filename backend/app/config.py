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
    SQLALCHEMY_ECHO = False



Config = DevelopmentConfig

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}