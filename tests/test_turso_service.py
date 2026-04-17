import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.turso_service import _push_local_snapshot


class _FakeRemoteConnection:
    def __init__(self):
        self.statements = []
        self.committed = False
        self.closed = False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return self

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class _FakeLibsqlModule:
    def __init__(self):
        self.connection = _FakeRemoteConnection()

    def connect(self, *_args, **_kwargs):
        return self.connection


class TursoServiceTests(unittest.TestCase):
    def test_push_local_snapshot_replays_sqlite_dump(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
            conn.execute("INSERT INTO users (email) VALUES ('alice@example.com')")
            conn.commit()
            conn.close()

            fake_libsql = _FakeLibsqlModule()
            with patch("services.turso_service.libsql", fake_libsql):
                _push_local_snapshot(
                    local_db_path=db_path,
                    turso_database_url="libsql://example.turso.io",
                    turso_auth_token="token",
                )

            statements = fake_libsql.connection.statements
            executed_sql = [stmt for stmt, _ in statements]
            self.assertIn("PRAGMA foreign_keys=OFF", executed_sql)
            self.assertIn('DROP TABLE IF EXISTS "users"', executed_sql)
            self.assertTrue(
                any(stmt.startswith("CREATE TABLE users") for stmt in executed_sql),
                "SQL dump should create users table on remote",
            )
            self.assertTrue(
                any("INSERT INTO \"users\"" in stmt for stmt in executed_sql),
                "SQL dump should insert users rows on remote",
            )
            self.assertTrue(fake_libsql.connection.committed)
            self.assertTrue(fake_libsql.connection.closed)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_push_local_snapshot_requires_existing_local_db(self):
        fake_libsql = _FakeLibsqlModule()
        with patch("services.turso_service.libsql", fake_libsql):
            with self.assertRaises(RuntimeError):
                _push_local_snapshot(
                    local_db_path="C:\\path\\does-not-exist.db",
                    turso_database_url="libsql://example.turso.io",
                    turso_auth_token="token",
                )

    def test_push_local_snapshot_can_sync_selected_tables(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
            conn.execute("CREATE TABLE portfolios (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            conn.execute("INSERT INTO users (email) VALUES ('alice@example.com')")
            conn.execute("INSERT INTO portfolios (name) VALUES ('Main')")
            conn.commit()
            conn.close()

            fake_libsql = _FakeLibsqlModule()
            with patch("services.turso_service.libsql", fake_libsql):
                _push_local_snapshot(
                    local_db_path=db_path,
                    turso_database_url="libsql://example.turso.io",
                    turso_auth_token="token",
                    table_names=["users"],
                )

            executed_sql = [stmt for stmt, _ in fake_libsql.connection.statements]
            self.assertIn('DROP TABLE IF EXISTS "users"', executed_sql)
            self.assertNotIn('DROP TABLE IF EXISTS "portfolios"', executed_sql)
            self.assertTrue(
                any(stmt.startswith("CREATE TABLE users") for stmt in executed_sql),
                "Selected table should be recreated",
            )
            self.assertFalse(
                any(stmt.startswith("CREATE TABLE portfolios") for stmt in executed_sql),
                "Non-selected table should not be touched",
            )
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


if __name__ == "__main__":
    unittest.main()
