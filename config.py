import os
import secrets
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit

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


def _as_turso_sqlalchemy_uri(turso_database_url: str) -> str:
    parsed = urlsplit(turso_database_url)
    if parsed.scheme not in {"libsql", "https", "http"} or not parsed.netloc:
        raise ValueError("TURSO_DATABASE_URL deve usar libsql://, https:// ou http://.")

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("secure", "true" if parsed.scheme in {"libsql", "https"} else "false")
    path = parsed.path or ""
    query_string = urlencode(query)
    uri = f"sqlite+libsql://{parsed.netloc}{path}"
    if query_string:
        uri = f"{uri}?{query_string}"
    return uri


def _resolve_database_settings():
    turso_database_url = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN")
    if not turso_database_url or not turso_auth_token:
        raise ValueError(
            "Projeto configurado para Turso-only. Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN."
        )

    return {
        "db_uri": _as_turso_sqlalchemy_uri(turso_database_url),
        "engine_options": {
            "pool_pre_ping": True,
            "connect_args": {"auth_token": turso_auth_token},
        },
        "turso_enabled": True,
        "turso_database_url": turso_database_url,
        "turso_auth_token": turso_auth_token,
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
