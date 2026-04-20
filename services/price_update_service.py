from datetime import datetime, timezone

from extensions import db
from models import Cryptocurrency
from services.coingecko_service import coins_markets


DEFAULT_BATCH_SIZE = 100


def _parse_last_updated(raw_value):
    if not raw_value:
        return None
    normalized = str(raw_value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def refresh_all_cryptocurrency_prices(vs_currency: str = "brl", batch_size: int = DEFAULT_BATCH_SIZE):
    cryptos = (
        Cryptocurrency.query
        .filter(Cryptocurrency.coingecko_id.isnot(None))
        .all()
    )
    if not cryptos:
        return {"updated": 0, "total": 0}

    by_coingecko_id = {crypto.coingecko_id: crypto for crypto in cryptos}
    coingecko_ids = sorted(by_coingecko_id.keys())
    updated_count = 0

    for start in range(0, len(coingecko_ids), batch_size):
        batch = coingecko_ids[start:start + batch_size]
        market_rows = coins_markets(
            vs_currency=vs_currency,
            ids=",".join(batch),
            order="market_cap_desc",
            per_page=len(batch),
            page=1,
        )
        now = datetime.utcnow()
        for row in market_rows:
            coin_id = row.get("id")
            crypto = by_coingecko_id.get(coin_id)
            if not crypto:
                continue
            crypto.current_price = row.get("current_price")
            crypto.current_marketcap = row.get("market_cap")
            crypto.price_change_percentage_24h = row.get("price_change_percentage_24h")
            crypto.last_updated = _parse_last_updated(row.get("last_updated")) or now
            updated_count += 1

    db.session.commit()
    return {"updated": updated_count, "total": len(cryptos)}
