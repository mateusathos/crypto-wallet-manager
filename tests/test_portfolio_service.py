import unittest
from types import SimpleNamespace

from services.portfolio_service import _build_summary


class PortfolioServiceTests(unittest.TestCase):
    def test_calculates_weighted_average_and_profit(self):
        transactions = [
            SimpleNamespace(cryptocurrency_id=1, quantity="2", price="100", type="compra"),
            SimpleNamespace(cryptocurrency_id=1, quantity="1", price="200", type="compra"),
            SimpleNamespace(cryptocurrency_id=1, quantity="1", price="250", type="venda"),
        ]
        crypto_map = {
            1: SimpleNamespace(
                id=1,
                name="Bitcoin",
                symbol="BTC",
                image_url="https://example.com/btc.png",
                current_price="150",
            )
        }

        summary = _build_summary(transactions, crypto_map)
        active = summary["actives"][0]

        self.assertAlmostEqual(active["quantity"], 2.0)
        self.assertAlmostEqual(active["average_purchase_price"], 133.33333333, places=4)
        self.assertAlmostEqual(summary["realized_profit"], 116.66666666, places=4)
        self.assertAlmostEqual(summary["unrealized_profit"], 33.33333333, places=4)
        self.assertAlmostEqual(summary["profit_total"], 150.0, places=4)
        self.assertAlmostEqual(summary["profit_percentage"], 37.5, places=4)

    def test_returns_empty_when_crypto_not_found(self):
        transactions = [
            SimpleNamespace(cryptocurrency_id=99, quantity="1", price="100", type="compra")
        ]

        summary = _build_summary(transactions, {})

        self.assertEqual(summary["actives"], [])
        self.assertEqual(summary["value"], 0.0)
        self.assertEqual(summary["profit_total"], 0.0)

    def test_returns_empty_when_transactions_missing(self):
        summary = _build_summary([], {})

        self.assertEqual(summary["actives"], [])
        self.assertEqual(summary["cost"], 0.0)
        self.assertEqual(summary["value"], 0.0)
        self.assertEqual(summary["profit_total"], 0.0)


if __name__ == "__main__":
    unittest.main()
