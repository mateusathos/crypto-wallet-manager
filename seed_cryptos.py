from app import app
from services.coingecko_service import coins_markets
from models import Cryptocurrency
from extensions import db

with app.app_context():
    # 🔥 1️⃣ Apaga todas as criptomoedas antes do seed
    Cryptocurrency.query.delete()
    db.session.commit()

    for i in range(1, 3):
        cryptos = coins_markets(per_page=100, page=i)

        for coin in cryptos:
            crypto = Cryptocurrency(
                name=coin["name"],
                symbol=coin["symbol"].upper(),
                coingecko_id=coin["id"],
                image_url=coin["image"],
                current_price=coin["current_price"],
                current_marketcap = coin["market_cap"],
                price_change_percentage_24h = coin["price_change_percentage_24h"]
            )
            db.session.add(crypto)

        db.session.commit()

    print("Top 100 criptomoedas recriadas com sucesso!")