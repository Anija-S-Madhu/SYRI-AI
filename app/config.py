"""Application configuration."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "syri.db").replace("\\", "/")


def _resolve_database_uri():
    """Resolve and normalize database URI ensuring SQLite paths are absolute."""
    uri = os.environ.get('DATABASE_URL')
    if not uri:
        return f'sqlite:///{DEFAULT_DB_PATH}'

    # If a relative sqlite URI was provided (e.g., sqlite:///instance/syri.db or sqlite:///syri.db),
    # resolve it against BASE_DIR or INSTANCE_DIR to prevent Flask-SQLAlchemy double-prepending instance_path
    if uri.startswith('sqlite:///') and not uri.startswith('sqlite:////'):
        rel_path = uri[len('sqlite:///'):]
        if rel_path in (':memory:', ''):
            return uri
        # If relative path is not already absolute
        if not os.path.isabs(rel_path):
            if rel_path.startswith('instance/') or rel_path.startswith('instance\\'):
                abs_path = os.path.join(BASE_DIR, rel_path)
            else:
                abs_path = os.path.join(INSTANCE_DIR, rel_path)
            return f'sqlite:///{abs_path.replace("\\", "/")}'
    return uri


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
