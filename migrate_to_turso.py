import argparse
import os
import shutil
import sqlite3

import libsql
from dotenv import load_dotenv


TABLE_ORDER = ["users", "cryptocurrencies", "portfolios", "transactions"]


def _reset_local_turso_state(local_db_path: str):
    absolute = os.path.abspath(local_db_path)
    for suffix in ("", "-info", "-shm", "-wal"):
        candidate = f"{absolute}{suffix}"
        if os.path.exists(candidate):
            os.remove(candidate)


def _prepare_local_snapshot(local_db_path: str, source_sqlite_path: str | None):
    os.makedirs(os.path.dirname(os.path.abspath(local_db_path)), exist_ok=True)
    if not source_sqlite_path:
        if not os.path.exists(local_db_path):
            raise RuntimeError(
                f"Nenhum snapshot local encontrado em {local_db_path}. "
                "Informe --from-sqlite para importar de um arquivo SQLite."
            )
        return

    source_abs = os.path.abspath(source_sqlite_path)
    if not os.path.exists(source_abs):
        raise RuntimeError(f"Arquivo SQLite de origem não encontrado: {source_abs}")

    _reset_local_turso_state(local_db_path)
    shutil.copyfile(source_abs, local_db_path)


def _push_sqlite_to_turso(local_db_path: str, turso_database_url: str, turso_auth_token: str):
    local_conn = sqlite3.connect(local_db_path)
    dump_lines = list(local_conn.iterdump())
    local_conn.close()

    remote_conn = libsql.connect(turso_database_url, auth_token=turso_auth_token)
    try:
        remote_conn.execute("PRAGMA foreign_keys=OFF")
        for table_name in reversed(TABLE_ORDER):
            remote_conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        remote_conn.execute("DROP TABLE IF EXISTS alembic_version")

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

        counts = {}
        for table_name in TABLE_ORDER:
            row = remote_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            counts[table_name] = int(row[0]) if row else 0
        return counts
    finally:
        remote_conn.close()


def main():
    load_dotenv()

    turso_database_url = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN")
    local_db_path = os.getenv("TURSO_LOCAL_DB_PATH", os.path.join("instance", "app.db"))
    if not turso_database_url or not turso_auth_token:
        raise RuntimeError("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN.")

    parser = argparse.ArgumentParser(
        description="Publica um snapshot SQLite para o Turso (Turso-only)."
    )
    parser.add_argument(
        "--from-sqlite",
        default=None,
        help="Caminho de um arquivo SQLite para copiar antes do envio ao Turso.",
    )
    args = parser.parse_args()

    _prepare_local_snapshot(local_db_path=local_db_path, source_sqlite_path=args.from_sqlite)
    counts = _push_sqlite_to_turso(
        local_db_path=local_db_path,
        turso_database_url=turso_database_url,
        turso_auth_token=turso_auth_token,
    )

    print("Envio para Turso concluído.")
    for table_name in TABLE_ORDER:
        print(f"- Turso {table_name}: {counts.get(table_name, 0)} registros")


if __name__ == "__main__":
    main()
