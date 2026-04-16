import os
import sqlite3

import libsql
from dotenv import load_dotenv


TABLE_ORDER = ["users", "cryptocurrencies", "portfolios", "transactions"]


def main():
    load_dotenv()

    turso_database_url = os.getenv("TURSO_DATABASE_URL")
    turso_auth_token = os.getenv("TURSO_AUTH_TOKEN")
    local_db_path = os.getenv("TURSO_LOCAL_DB_PATH", os.path.join("instance", "app.db"))

    if not turso_database_url or not turso_auth_token:
        raise RuntimeError("Defina TURSO_DATABASE_URL e TURSO_AUTH_TOKEN.")

    if not os.path.exists(local_db_path):
        raise RuntimeError(f"Banco local não encontrado: {local_db_path}")

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

        print("Envio ao Turso concluído.")
        for table_name in TABLE_ORDER:
            count = remote_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            print(f"- {table_name}: {count}")
    finally:
        remote_conn.close()


if __name__ == "__main__":
    main()
