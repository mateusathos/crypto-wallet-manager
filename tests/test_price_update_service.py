import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.price_update_service import (
    _parse_last_updated,
    refresh_all_cryptocurrency_prices_remote_first,
)


class PriceUpdateServiceTests(unittest.TestCase):
    def test_parse_last_updated_iso(self):
        parsed = _parse_last_updated("2026-04-16T12:34:56.000Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.minute, 34)

    def test_parse_last_updated_invalid(self):
        parsed = _parse_last_updated("not-a-date")
        self.assertIsNone(parsed)

    def test_parse_last_updated_with_offset_normalizes_to_utc(self):
        parsed = _parse_last_updated("2026-04-16T12:34:56+02:00")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.hour, 10)
        self.assertEqual(parsed.minute, 34)

    def test_remote_first_updates_turso_before_local_commit(self):
        crypto = SimpleNamespace(
            coingecko_id="bitcoin",
            current_price=None,
            current_marketcap=None,
            price_change_percentage_24h=None,
            last_updated=None,
        )
        events = []

        def remote_update(**_kwargs):
            events.append("remote")
            return 1

        def local_commit():
            events.append("local")

        app = SimpleNamespace(
            config={
                "TURSO_DATABASE_URL": "libsql://example.turso.io",
                "TURSO_AUTH_TOKEN": "token",
            }
        )

        with patch(
                "services.price_update_service._cryptocurrencies_with_coingecko_ids",
                return_value=[crypto],
            ), \
            patch(
                "services.price_update_service.coins_markets",
                return_value=[
                    {
                        "id": "bitcoin",
                        "current_price": 100,
                        "market_cap": 200,
                        "price_change_percentage_24h": 1.5,
                        "last_updated": "2026-06-08T12:30:00.000Z",
                    }
                ],
            ), \
            patch(
                "services.price_update_service.update_remote_cryptocurrency_prices",
                side_effect=remote_update,
            ), \
            patch("services.price_update_service.db.session.commit", side_effect=local_commit):
            result = refresh_all_cryptocurrency_prices_remote_first(app)

        self.assertEqual(events, ["remote", "local"])
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["remote_updated"], 1)
        self.assertEqual(crypto.current_price, 100)


if __name__ == "__main__":
    unittest.main()
