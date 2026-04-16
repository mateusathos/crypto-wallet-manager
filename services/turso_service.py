import os
from typing import Optional

try:
    import libsql
except ImportError:  # pragma: no cover - depends on environment
    libsql = None


def _is_invalid_local_state_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "invalid local state" in message
        or "metadata file does not" in message
        or "db file exists but metadata file does not" in message
    )


def _build_sync_connection(
    local_db_path: str,
    turso_database_url: str,
    turso_auth_token: str,
    sync_interval_seconds: int,
):
    if libsql is None:
        raise RuntimeError(
            "Pacote 'libsql' não está instalado. Rode: pip install libsql"
        )

    os.makedirs(os.path.dirname(os.path.abspath(local_db_path)), exist_ok=True)
    connect_args = {
        "sync_url": turso_database_url,
        "auth_token": turso_auth_token,
    }
    if sync_interval_seconds > 0:
        connect_args["sync_interval"] = sync_interval_seconds
    return libsql.connect(local_db_path, **connect_args)


def _remove_sync_files(local_db_path: str):
    absolute_path = os.path.abspath(local_db_path)
    for suffix in ("", "-info", "-shm", "-wal"):
        candidate = f"{absolute_path}{suffix}"
        if os.path.exists(candidate):
            os.remove(candidate)


def _connect_and_sync(local_db_path, turso_database_url, turso_auth_token, sync_interval_seconds):
    conn = _build_sync_connection(
        local_db_path=local_db_path,
        turso_database_url=turso_database_url,
        turso_auth_token=turso_auth_token,
        sync_interval_seconds=sync_interval_seconds,
    )
    conn.sync()
    return conn


def init_turso_sync(app):
    if not app.config.get("TURSO_ENABLED", False):
        return None

    local_db_path = app.config["TURSO_LOCAL_DB_PATH"]
    sync_interval_seconds = int(app.config.get("TURSO_SYNC_INTERVAL_SECONDS", 0))
    try:
        conn = _connect_and_sync(
            local_db_path=local_db_path,
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
            sync_interval_seconds=sync_interval_seconds,
        )
    except ValueError as exc:
        if not _is_invalid_local_state_error(exc):
            raise
        _remove_sync_files(local_db_path)
        conn = _connect_and_sync(
            local_db_path=local_db_path,
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
            sync_interval_seconds=sync_interval_seconds,
        )
    app.extensions["turso_sync_conn"] = conn
    return conn


def sync_now(app) -> bool:
    conn: Optional[object] = app.extensions.get("turso_sync_conn")
    if conn is None:
        return False
    try:
        conn.sync()
    except ValueError as exc:
        if not _is_invalid_local_state_error(exc):
            raise
        try:
            conn.close()
        except Exception:
            pass
        local_db_path = app.config["TURSO_LOCAL_DB_PATH"]
        _remove_sync_files(local_db_path)
        conn = _connect_and_sync(
            local_db_path=local_db_path,
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
            sync_interval_seconds=int(app.config.get("TURSO_SYNC_INTERVAL_SECONDS", 0)),
        )
        app.extensions["turso_sync_conn"] = conn
    return True
