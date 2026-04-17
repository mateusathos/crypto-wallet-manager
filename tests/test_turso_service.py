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

    def execute(self, statement):
        self.statements.append(statement)
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
            self.assertIn("PRAGMA foreign_keys=OFF", statements)
            self.assertIn('DROP TABLE IF EXISTS "users"', statements)
            self.assertTrue(
                any(stmt.startswith("CREATE TABLE users") for stmt in statements),
                "SQL dump should create users table on remote",
            )
            self.assertTrue(
                any("INSERT INTO \"users\"" in stmt for stmt in statements),
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


if __name__ == "__main__":
    unittest.main()
