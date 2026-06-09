import os
import sqlite3
import threading
from datetime import datetime
from typing import Optional

try:
    import libsql
except ImportError:  # pragma: no cover - depends on environment
    libsql = None


TABLE_SYNC_ORDER = ["users", "cryptocurrencies", "portfolios", "transactions"]


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


def _sqlite_datetime(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    return value


def _ordered_table_names(table_names) -> list[str]:
    unique_names = {str(name) for name in (table_names or [])}
    ordered = [name for name in TABLE_SYNC_ORDER if name in unique_names]
    remaining = sorted(name for name in unique_names if name not in TABLE_SYNC_ORDER)
    return ordered + remaining


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


def _local_table_schema(local_conn: sqlite3.Connection, table_name: str) -> str:
    row = local_conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()
    if not row or not row[0]:
        raise RuntimeError(f"Tabela local não encontrada para sync: {table_name}")
    return str(row[0])


def _replace_remote_table(local_conn, remote_conn, table_name: str):
    schema_sql = _local_table_schema(local_conn, table_name)
    quoted_table_name = _quote_identifier(table_name)
    remote_conn.execute(f"DROP TABLE IF EXISTS {quoted_table_name}")
    remote_conn.execute(schema_sql)

    cursor = local_conn.execute(f"SELECT * FROM {quoted_table_name}")
    columns = [str(col[0]) for col in (cursor.description or [])]
    rows = cursor.fetchall()
    if not rows:
        return

    columns_sql = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = (
        f"INSERT INTO {quoted_table_name} ({columns_sql}) VALUES ({placeholders})"
    )
    for row in rows:
        remote_conn.execute(insert_sql, tuple(row))


def _primary_key_columns(local_conn: sqlite3.Connection, table_name: str) -> list[str]:
    quoted_table_name = _quote_identifier(table_name)
    rows = local_conn.execute(f"PRAGMA table_info({quoted_table_name})").fetchall()
    pk_rows = sorted(
        ((int(row[5]), str(row[1])) for row in rows if int(row[5] or 0) > 0),
        key=lambda item: item[0],
    )
    return [name for _position, name in pk_rows]


def _upsert_remote_table(local_conn, remote_conn, table_name: str):
    quoted_table_name = _quote_identifier(table_name)
    cursor = local_conn.execute(f"SELECT * FROM {quoted_table_name}")
    columns = [str(col[0]) for col in (cursor.description or [])]
    rows = cursor.fetchall()
    if not rows:
        return

    pk_columns = _primary_key_columns(local_conn, table_name)
    if not pk_columns:
        raise RuntimeError(f"Tabela sem chave primária para upsert: {table_name}")

    columns_sql = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _column in columns)
    conflict_columns = ", ".join(_quote_identifier(column) for column in pk_columns)
    update_columns = [column for column in columns if column not in set(pk_columns)]

    if update_columns:
        update_sql = ", ".join(
            f"{_quote_identifier(column)} = excluded.{_quote_identifier(column)}"
            for column in update_columns
        )
        conflict_action = f"DO UPDATE SET {update_sql}"
    else:
        conflict_action = "DO NOTHING"

    insert_sql = (
        f"INSERT INTO {quoted_table_name} ({columns_sql}) VALUES ({placeholders}) "
        f"ON CONFLICT({conflict_columns}) {conflict_action}"
    )
    for row in rows:
        remote_conn.execute(insert_sql, tuple(row))


def _push_local_snapshot(
    local_db_path: str,
    turso_database_url: str,
    turso_auth_token: str,
    table_names: list[str] | None = None,
):
    if libsql is None:
        raise RuntimeError(
            "Pacote 'libsql' não está instalado. Rode: pip install libsql"
        )
    if not os.path.exists(local_db_path):
        raise RuntimeError(f"Banco local não encontrado para sync: {local_db_path}")

    tables_to_sync = _ordered_table_names(
        table_names if table_names is not None else _list_local_tables(local_db_path)
    )
    if not tables_to_sync:
        return

    local_conn = sqlite3.connect(local_db_path)
    remote_conn = libsql.connect(turso_database_url, auth_token=turso_auth_token)
    try:
        remote_conn.execute("PRAGMA foreign_keys=OFF")
        for table_name in reversed(tables_to_sync):
            remote_conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)}")
        for table_name in tables_to_sync:
            _replace_remote_table(local_conn, remote_conn, table_name)
        remote_conn.commit()
    finally:
        local_conn.close()
        remote_conn.close()


def _upsert_local_snapshot(
    local_db_path: str,
    turso_database_url: str,
    turso_auth_token: str,
    table_names: list[str],
):
    if libsql is None:
        raise RuntimeError(
            "Pacote 'libsql' não está instalado. Rode: pip install libsql"
        )
    if not os.path.exists(local_db_path):
        raise RuntimeError(f"Banco local não encontrado para sync: {local_db_path}")

    tables_to_sync = _ordered_table_names(table_names)
    if not tables_to_sync:
        return

    local_conn = sqlite3.connect(local_db_path)
    remote_conn = libsql.connect(turso_database_url, auth_token=turso_auth_token)
    try:
        for table_name in tables_to_sync:
            _upsert_remote_table(local_conn, remote_conn, table_name)
        remote_conn.commit()
    finally:
        local_conn.close()
        remote_conn.close()


def update_remote_cryptocurrency_prices(
    turso_database_url: str,
    turso_auth_token: str,
    price_updates: list[dict],
) -> int:
    if libsql is None:
        raise RuntimeError(
            "Pacote 'libsql' não está instalado. Rode: pip install libsql"
        )
    if not price_updates:
        return 0

    remote_conn = libsql.connect(turso_database_url, auth_token=turso_auth_token)
    try:
        for update in price_updates:
            remote_conn.execute(
                """
                UPDATE cryptocurrencies
                SET current_price = ?,
                    current_marketcap = ?,
                    price_change_percentage_24h = ?,
                    last_updated = ?
                WHERE coingecko_id = ?
                """,
                (
                    update["current_price"],
                    update["current_marketcap"],
                    update["price_change_percentage_24h"],
                    _sqlite_datetime(update["last_updated"]),
                    update["coingecko_id"],
                ),
            )
        remote_conn.commit()
        return len(price_updates)
    finally:
        remote_conn.close()


def _remote_execute_transaction(
    turso_database_url: str,
    turso_auth_token: str,
    statements: list[tuple[str, tuple]],
):
    if libsql is None:
        raise RuntimeError(
            "Pacote 'libsql' não está instalado. Rode: pip install libsql"
        )
    if not statements:
        return

    remote_conn = libsql.connect(turso_database_url, auth_token=turso_auth_token)
    try:
        for statement, params in statements:
            remote_conn.execute(statement, params)
        remote_conn.commit()
    finally:
        remote_conn.close()


def _date_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _remote_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def create_remote_portfolio(turso_database_url: str, turso_auth_token: str, portfolio):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                INSERT INTO portfolios (id, name, icon, user_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    icon = excluded.icon,
                    user_id = excluded.user_id
                """,
                (portfolio.id, portfolio.name, portfolio.icon, portfolio.user_id),
            )
        ],
    )


def update_remote_portfolio(turso_database_url: str, turso_auth_token: str, portfolio):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                UPDATE portfolios
                SET name = ?, icon = ?
                WHERE id = ? AND user_id = ?
                """,
                (portfolio.name, portfolio.icon, portfolio.id, portfolio.user_id),
            )
        ],
    )


def delete_remote_portfolio(
    turso_database_url: str,
    turso_auth_token: str,
    portfolio_id: int,
    user_id: int,
):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                DELETE FROM transactions
                WHERE portfolio_id IN (
                    SELECT id FROM portfolios WHERE id = ? AND user_id = ?
                )
                """,
                (portfolio_id, user_id),
            ),
            (
                "DELETE FROM portfolios WHERE id = ? AND user_id = ?",
                (portfolio_id, user_id),
            ),
        ],
    )


def create_remote_transaction(
    turso_database_url: str,
    turso_auth_token: str,
    transaction,
):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                INSERT INTO transactions (
                    id,
                    portfolio_id,
                    cryptocurrency_id,
                    quantity,
                    price,
                    fee,
                    type,
                    transaction_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    portfolio_id = excluded.portfolio_id,
                    cryptocurrency_id = excluded.cryptocurrency_id,
                    quantity = excluded.quantity,
                    price = excluded.price,
                    fee = excluded.fee,
                    type = excluded.type,
                    transaction_date = excluded.transaction_date
                """,
                (
                    transaction.id,
                    transaction.portfolio_id,
                    transaction.cryptocurrency_id,
                    _remote_value(transaction.quantity),
                    _remote_value(transaction.price),
                    _remote_value(transaction.fee or 0),
                    transaction.type,
                    _date_value(transaction.transaction_date),
                ),
            )
        ],
    )


def update_remote_transaction(
    turso_database_url: str,
    turso_auth_token: str,
    transaction,
    user_id: int,
):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                UPDATE transactions
                SET quantity = ?,
                    price = ?,
                    type = ?,
                    transaction_date = ?
                WHERE id = ?
                  AND portfolio_id IN (
                      SELECT id FROM portfolios WHERE user_id = ?
                  )
                """,
                (
                    _remote_value(transaction.quantity),
                    _remote_value(transaction.price),
                    transaction.type,
                    _date_value(transaction.transaction_date),
                    transaction.id,
                    user_id,
                ),
            )
        ],
    )


def delete_remote_transaction(
    turso_database_url: str,
    turso_auth_token: str,
    transaction_id: int,
    user_id: int,
):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                DELETE FROM transactions
                WHERE id = ?
                  AND portfolio_id IN (
                      SELECT id FROM portfolios WHERE user_id = ?
                  )
                """,
                (transaction_id, user_id),
            )
        ],
    )


def delete_remote_asset_transactions(
    turso_database_url: str,
    turso_auth_token: str,
    portfolio_id: int,
    user_id: int,
    cryptocurrency_id: int,
):
    _remote_execute_transaction(
        turso_database_url,
        turso_auth_token,
        [
            (
                """
                DELETE FROM transactions
                WHERE portfolio_id = ?
                  AND cryptocurrency_id = ?
                  AND portfolio_id IN (
                      SELECT id FROM portfolios WHERE user_id = ?
                  )
                """,
                (portfolio_id, cryptocurrency_id, user_id),
            )
        ],
    )


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


def push_snapshot_now(app, table_names: list[str] | None = None) -> bool:
    if not app.config.get("TURSO_ENABLED", False):
        return False

    lock = _get_sync_lock(app)
    with lock:
        _push_local_snapshot(
            local_db_path=app.config["TURSO_LOCAL_DB_PATH"],
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
            table_names=table_names,
        )
        conn: Optional[object] = app.extensions.get("turso_sync_conn")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            app.extensions["turso_sync_conn"] = None
    return True


def upsert_snapshot_now(app, table_names: list[str]) -> bool:
    if not app.config.get("TURSO_ENABLED", False):
        return False

    lock = _get_sync_lock(app)
    with lock:
        _upsert_local_snapshot(
            local_db_path=app.config["TURSO_LOCAL_DB_PATH"],
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
            table_names=table_names,
        )
        conn: Optional[object] = app.extensions.get("turso_sync_conn")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            app.extensions["turso_sync_conn"] = None
    return True
