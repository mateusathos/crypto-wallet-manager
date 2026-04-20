import unittest
from datetime import datetime, timezone

from routes.criptomoedas import format_last_updated


class CriptomoedasRouteTests(unittest.TestCase):
    def test_format_last_updated_converts_utc_to_brasilia(self):
        value = datetime(2026, 4, 20, 15, 0, 0)
        formatted = format_last_updated(value)
        self.assertEqual(formatted, "20/04/2026 12:00:00")

    def test_format_last_updated_accepts_aware_datetime(self):
        value = datetime(2026, 4, 20, 15, 0, 0, tzinfo=timezone.utc)
        formatted = format_last_updated(value)
        self.assertEqual(formatted, "20/04/2026 12:00:00")

    def test_format_last_updated_empty_value(self):
        self.assertEqual(format_last_updated(None), "Não informado")


if __name__ == "__main__":
    unittest.main()
