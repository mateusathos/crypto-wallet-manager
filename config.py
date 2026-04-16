import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


def _get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_sqlite_uri(db_path: str) -> str:
    absolute_path = os.path.abspath(db_path)
    normalized = absolute_path.replace("\\", "/")
    return f"sqlite:///{normalized}"


def _default_sqlite_path() -> str:
    if os.getenv("VERCEL"):
        return os.path.join("/tmp", "app.db")
    return os.path.join("instance", "app.db")


def _resolve_database_settings():
    turso_database_url = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN")
    if not turso_database_url or not turso_auth_token:
        raise ValueError(
            "Projeto configurado para Turso-only. Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN."
        )

    turso_local_db_path = os.getenv("TURSO_LOCAL_DB_PATH", _default_sqlite_path())
    os.makedirs(os.path.dirname(os.path.abspath(turso_local_db_path)), exist_ok=True)

    return {
        "db_uri": _as_sqlite_uri(turso_local_db_path),
        "engine_options": {"pool_pre_ping": True},
        "turso_enabled": True,
        "turso_database_url": turso_database_url,
        "turso_auth_token": turso_auth_token,
        "turso_local_db_path": turso_local_db_path,
        "turso_sync_interval_seconds": _get_int_env("TURSO_SYNC_INTERVAL_SECONDS", 30),
    }


_DATABASE_SETTINGS = _resolve_database_settings()


class Config:
    ENVIRONMENT = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    DEBUG = _get_bool_env("FLASK_DEBUG", ENVIRONMENT in {"development", "dev"})

    SQLALCHEMY_DATABASE_URI = _DATABASE_SETTINGS["db_uri"]
    SQLALCHEMY_ENGINE_OPTIONS = _DATABASE_SETTINGS["engine_options"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TURSO_ENABLED = _DATABASE_SETTINGS["turso_enabled"]
    TURSO_DATABASE_URL = _DATABASE_SETTINGS["turso_database_url"]
    TURSO_AUTH_TOKEN = _DATABASE_SETTINGS["turso_auth_token"]
    TURSO_LOCAL_DB_PATH = _DATABASE_SETTINGS["turso_local_db_path"]
    TURSO_SYNC_INTERVAL_SECONDS = _DATABASE_SETTINGS["turso_sync_interval_seconds"]
    CRON_SECRET = os.getenv("CRON_SECRET")

    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(64)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _get_bool_env(
        "SESSION_COOKIE_SECURE",
        ENVIRONMENT in {"production", "prod"},
    )
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=_get_int_env("SESSION_LIFETIME_HOURS", 12)
    )
