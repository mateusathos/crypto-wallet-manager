import os
import sqlite3
import threading
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


def _is_wal_frame_conflict_error(exc: Exception) -> bool:
    return "wal frame insert conflict" in str(exc).lower()


def _is_recoverable_sync_error(exc: Exception) -> bool:
    return _is_invalid_local_state_error(exc) or _is_wal_frame_conflict_error(exc)


def _get_sync_lock(app):
    lock = app.extensions.get("turso_sync_lock")
    if lock is None:
        lock = threading.RLock()
        app.extensions["turso_sync_lock"] = lock
    return lock


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


def _quote_identifier(identifier: str) -> str:
    escaped = str(identifier).replace('"', '""')
    return f'"{escaped}"'


def _iter_sqlite_dump(local_db_path: str):
    local_conn = sqlite3.connect(local_db_path)
    try:
        return list(local_conn.iterdump())
    finally:
        local_conn.close()


def _list_local_tables(local_db_path: str):
    local_conn = sqlite3.connect(local_db_path)
    try:
        rows = local_conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        return [str(row[0]) for row in rows]
    finally:
        local_conn.close()


def _push_local_snapshot(local_db_path: str, turso_database_url: str, turso_auth_token: str):
    if libsql is None:
        raise RuntimeError(
            "Pacote 'libsql' não está instalado. Rode: pip install libsql"
        )
    if not os.path.exists(local_db_path):
        raise RuntimeError(f"Banco local não encontrado para sync: {local_db_path}")

    dump_lines = _iter_sqlite_dump(local_db_path)
    table_names = _list_local_tables(local_db_path)
    remote_conn = libsql.connect(turso_database_url, auth_token=turso_auth_token)
    try:
        remote_conn.execute("PRAGMA foreign_keys=OFF")
        for table_name in reversed(table_names):
            remote_conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)}")

        for line in dump_lines:
            stmt = line.strip()
            if not stmt:
                continue
            if stmt in {"BEGIN TRANSACTION;", "COMMIT;"}:
                continue
            if stmt.startswith("CREATE TABLE sqlite_sequence"):
                continue
            if stmt.startswith("INSERT INTO \"sqlite_sequence\""):
                continue
            remote_conn.execute(stmt)

        remote_conn.commit()
    finally:
        remote_conn.close()


def init_turso_sync(app):
    if not app.config.get("TURSO_ENABLED", False):
        return None

    lock = _get_sync_lock(app)
    with lock:
        conn: Optional[object] = app.extensions.get("turso_sync_conn")
        if conn is not None:
            return conn

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
            if not _is_recoverable_sync_error(exc):
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
    if not app.config.get("TURSO_ENABLED", False):
        return False

    lock = _get_sync_lock(app)
    with lock:
        conn: Optional[object] = app.extensions.get("turso_sync_conn")
        if conn is None:
            conn = init_turso_sync(app)
            if conn is None:
                return False

        try:
            conn.sync()
        except ValueError as exc:
            if not _is_recoverable_sync_error(exc):
                raise
            try:
                conn.close()
            except Exception:
                pass

            local_db_path = app.config["TURSO_LOCAL_DB_PATH"]
            sync_interval_seconds = int(app.config.get("TURSO_SYNC_INTERVAL_SECONDS", 0))
            try:
                conn = _connect_and_sync(
                    local_db_path=local_db_path,
                    turso_database_url=app.config["TURSO_DATABASE_URL"],
                    turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
                    sync_interval_seconds=sync_interval_seconds,
                )
            except ValueError as reconnect_exc:
                if not _is_recoverable_sync_error(reconnect_exc):
                    raise
                _remove_sync_files(local_db_path)
                conn = _connect_and_sync(
                    local_db_path=local_db_path,
                    turso_database_url=app.config["TURSO_DATABASE_URL"],
                    turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
                    sync_interval_seconds=sync_interval_seconds,
                )
            app.extensions["turso_sync_conn"] = conn
    return True


def push_snapshot_now(app) -> bool:
    if not app.config.get("TURSO_ENABLED", False):
        return False

    lock = _get_sync_lock(app)
    with lock:
        _push_local_snapshot(
            local_db_path=app.config["TURSO_LOCAL_DB_PATH"],
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
        )
        conn: Optional[object] = app.extensions.get("turso_sync_conn")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            app.extensions["turso_sync_conn"] = None
    return True
