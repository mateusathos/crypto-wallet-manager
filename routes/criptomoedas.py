from datetime import timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template

from models import Cryptocurrency

crypto_bp = Blueprint("crypto", __name__)
DISPLAY_TIMEZONE = ZoneInfo("America/Sao_Paulo")


def brl_format(value) -> str:
    amount = Decimal(str(value or 0))
    if amount > Decimal("0.01"):
        return (
            f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    return f"R$ {amount}".replace(".", ",")


def format_last_updated(value) -> str:
    if not value:
        return "Não informado"

    utc_value = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return utc_value.astimezone(DISPLAY_TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")


@crypto_bp.route("/criptomoedas")
def list_cryptos():
    cryptos = Cryptocurrency.query.all()
    crypto_rows = []

    for crypto in cryptos:
        change_24h = float(crypto.price_change_percentage_24h or 0)
        crypto_rows.append(
            {
                "name": crypto.name,
                "symbol": crypto.symbol,
                "coingecko_id": crypto.coingecko_id,
                "image_url": crypto.image_url,
                "current_price_brl": brl_format(crypto.current_price),
                "current_marketcap_brl": brl_format(crypto.current_marketcap),
                "price_change_percentage_24h": change_24h,
                "last_updated": format_last_updated(crypto.last_updated),
            }
        )

    return render_template("criptomoedas.html", cryptos=crypto_rows)
