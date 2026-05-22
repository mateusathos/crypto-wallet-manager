from flask import Blueprint, jsonify

from models import Cryptocurrency
from routes.criptomoedas import format_last_updated


api_cryptocurrencies_bp = Blueprint(
    "api_cryptocurrencies",
    __name__,
    url_prefix="/api/cryptocurrencies",
)


def _crypto_payload(crypto: Cryptocurrency):
    return {
        "id": crypto.id,
        "name": crypto.name,
        "symbol": crypto.symbol,
        "coingecko_id": crypto.coingecko_id,
        "image_url": crypto.image_url,
        "current_price": float(crypto.current_price or 0),
        "current_marketcap": float(crypto.current_marketcap or 0),
        "price_change_percentage_24h": float(
            crypto.price_change_percentage_24h or 0
        ),
        "last_updated": (
            crypto.last_updated.isoformat()
            if crypto.last_updated
            else None
        ),
        "last_updated_formatted": format_last_updated(crypto.last_updated),
    }

@api_cryptocurrencies_bp.get("")
def list_cryptocurrencies():
    cryptos = Cryptocurrency.query.order_by(Cryptocurrency.id).all()

    return jsonify({
        "cryptocurrencies": [
            _crypto_payload(crypto)
            for crypto in cryptos
        ]
    })