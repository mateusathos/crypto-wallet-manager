import unittest

from services.portfolio_icons import DEFAULT_PORTFOLIO_ICON, normalize_portfolio_icon


class PortfolioIconTests(unittest.TestCase):
    def test_accepts_known_icon(self):
        self.assertEqual(normalize_portfolio_icon("rocket"), "rocket")

    def test_falls_back_to_default_for_unknown_icon(self):
        self.assertEqual(normalize_portfolio_icon("not-real"), DEFAULT_PORTFOLIO_ICON)

    def test_falls_back_to_default_for_empty_icon(self):
        self.assertEqual(normalize_portfolio_icon(""), DEFAULT_PORTFOLIO_ICON)


if __name__ == "__main__":
    unittest.main()
