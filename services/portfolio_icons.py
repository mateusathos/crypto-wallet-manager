DEFAULT_PORTFOLIO_ICON = "wallet"

PORTFOLIO_ICON_OPTIONS = [
    {"name": "wallet", "label": "Carteira"},
    {"name": "trending-up", "label": "Crescimento"},
    {"name": "shield", "label": "Reserva"},
    {"name": "rocket", "label": "Agressivo"},
    {"name": "coins", "label": "Moedas"},
    {"name": "target", "label": "Meta"},
    {"name": "bitcoin", "label": "Bitcoin"},
    {"name": "gem", "label": "Altcoins"},
]

_PORTFOLIO_ICON_NAMES = {option["name"] for option in PORTFOLIO_ICON_OPTIONS}


def normalize_portfolio_icon(raw_icon):
    icon = str(raw_icon or "").strip()
    if icon in _PORTFOLIO_ICON_NAMES:
        return icon
    return DEFAULT_PORTFOLIO_ICON
