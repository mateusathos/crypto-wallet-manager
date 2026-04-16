import unittest

from services.price_update_service import _parse_last_updated


class PriceUpdateServiceTests(unittest.TestCase):
    def test_parse_last_updated_iso(self):
        parsed = _parse_last_updated("2026-04-16T12:34:56.000Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.minute, 34)

    def test_parse_last_updated_invalid(self):
        parsed = _parse_last_updated("not-a-date")
        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()
