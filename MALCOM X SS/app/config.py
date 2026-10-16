import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    DEMO_DATABASE = False
    SECRET_KEY = os.getenv("SECRET_KEY", "mx_school_secret_key_2026")
    SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "").lower() in {"1", "true", "yes"}
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL")
        or os.getenv("MYSQL_URL")
        or f"sqlite:///{BASE_DIR / 'mx_sms.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    PRIVATE_UPLOAD_FOLDER = BASE_DIR / "instance" / "uploads"
    JSON_SORT_KEYS = False
    BOOTSTRAP_BOOTSWATCH = "flatly"


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SEED_DEMO_DATA = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SERVER_NAME = "localhost"


class DemoConfig(Config):
    DEMO_DATABASE = True
    SEED_DEMO_DATA = False
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'mx_sms_demo.db'}"
    SECRET_KEY = "mx_sms_local_demo_only_secret_key"
    WTF_CSRF_ENABLED = False
