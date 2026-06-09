import importlib
import os
import sys
import unittest


class ConfigTests(unittest.TestCase):
    def test_turso_url_is_converted_to_sqlalchemy_libsql_uri(self):
        os.environ.setdefault("TURSO_DATABASE_URL", "libsql://example.turso.io")
        os.environ.setdefault("TURSO_AUTH_TOKEN", "token")
        sys.modules.pop("config", None)

        config = importlib.import_module("config")

        self.assertEqual(
            config._as_turso_sqlalchemy_uri("libsql://example.turso.io"),
            "sqlite+libsql://example.turso.io?secure=true",
        )

    def test_http_turso_url_uses_insecure_flag(self):
        os.environ.setdefault("TURSO_DATABASE_URL", "libsql://example.turso.io")
        os.environ.setdefault("TURSO_AUTH_TOKEN", "token")
        sys.modules.pop("config", None)

        config = importlib.import_module("config")

        self.assertEqual(
            config._as_turso_sqlalchemy_uri("http://localhost:8080"),
            "sqlite+libsql://localhost:8080?secure=false",
        )


if __name__ == "__main__":
    unittest.main()
