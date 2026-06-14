from datetime import timedelta
import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class BaseConfig:
    DEBUG = False
    TESTING = False
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
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 7))
    )
    # Active la vérification blocklist dans le callback @jwt.token_in_blocklist_loader
    JWT_BLACKLIST_ENABLED = True
    SESSION_INACTIVITY_TIMEOUT = int(
        os.environ.get("SESSION_INACTIVITY_TIMEOUT_MINUTES", 30)
    )
    
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