from datetime import datetime, timezone

from extensions import db
from models import Cryptocurrency
from services.coingecko_service import coins_markets
from services.turso_service import update_remote_cryptocurrency_prices


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


def _build_price_updates(cryptos, vs_currency: str, batch_size: int):
    if not cryptos:
        return []

    by_coingecko_id = {crypto.coingecko_id: crypto for crypto in cryptos}
    coingecko_ids = sorted(by_coingecko_id.keys())
    updates = []

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
            if coin_id not in by_coingecko_id:
                continue
            last_updated = _parse_last_updated(row.get("last_updated")) or now
            updates.append(
                {
                    "coingecko_id": coin_id,
                    "current_price": row.get("current_price"),
                    "current_marketcap": row.get("market_cap"),
                    "price_change_percentage_24h": row.get(
                        "price_change_percentage_24h"
                    ),
                    "last_updated": last_updated,
                }
            )

    return updates


def _apply_local_price_updates(cryptos, price_updates):
    by_coingecko_id = {crypto.coingecko_id: crypto for crypto in cryptos}
    updated_count = 0

    for update in price_updates:
        crypto = by_coingecko_id.get(update["coingecko_id"])
        if not crypto:
            continue
        crypto.current_price = update["current_price"]
        crypto.current_marketcap = update["current_marketcap"]
        crypto.price_change_percentage_24h = update["price_change_percentage_24h"]
        crypto.last_updated = update["last_updated"]
        updated_count += 1

    db.session.commit()
    return updated_count


def _cryptocurrencies_with_coingecko_ids():
    return (
        Cryptocurrency.query
        .filter(Cryptocurrency.coingecko_id.isnot(None))
        .all()
    )


def refresh_all_cryptocurrency_prices_remote_first(
    app,
    vs_currency: str = "brl",
    batch_size: int = DEFAULT_BATCH_SIZE,
):
    cryptos = _cryptocurrencies_with_coingecko_ids()
    if not cryptos:
        return {"updated": 0, "total": 0, "remote_updated": 0}

    price_updates = _build_price_updates(
        cryptos=cryptos,
        vs_currency=vs_currency,
        batch_size=batch_size,
    )

    try:
        remote_updated = update_remote_cryptocurrency_prices(
            turso_database_url=app.config["TURSO_DATABASE_URL"],
            turso_auth_token=app.config["TURSO_AUTH_TOKEN"],
            price_updates=price_updates,
        )
    except Exception:
        db.session.rollback()
        raise

    updated_count = _apply_local_price_updates(cryptos, price_updates)
    return {
        "updated": updated_count,
        "total": len(cryptos),
        "remote_updated": remote_updated,
    }
