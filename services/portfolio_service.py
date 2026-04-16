from collections import defaultdict
from decimal import Decimal

from extensions import db
from models import Cryptocurrency, Transaction


def _empty_summary():
    return {
        "actives": [],
        "cost": 0.0,
        "value": 0.0,
        "unrealized_profit": 0.0,
        "realized_profit": 0.0,
        "profit_total": 0.0,
        "profit_percentage": 0.0,
        "invested_base": 0.0,
    }


def _build_summary(transactions, crypto_map):
    if not transactions:
        return _empty_summary()

    grouped = defaultdict(list)
    for txn in transactions:
        grouped[txn.cryptocurrency_id].append(txn)

    actives = []
    total_cost = Decimal("0")
    total_value = Decimal("0")
    total_realized = Decimal("0")
    total_buy_cost = Decimal("0")

    for crypto_id, items in grouped.items():
        crypto = crypto_map.get(crypto_id)
        if not crypto:
            continue

        qty = Decimal("0")
        cost = Decimal("0")
        realized = Decimal("0")
        buy_cost = Decimal("0")

        for txn in items:
            quantity = Decimal(str(txn.quantity))
            price = Decimal(str(txn.price))
            txn_type = (str(txn.type) or "").strip().lower()

            if txn_type == "compra":
                qty += quantity
                cost += price * quantity
                buy_cost += price * quantity
            elif txn_type == "venda":
                avg = (cost / qty) if qty > 0 else Decimal("0")
                realized += (price * quantity) - (avg * quantity)
                qty -= quantity
                cost -= avg * quantity

        current_price = Decimal(str(crypto.current_price or 0))
        current_value = current_price * qty
        unrealized = current_value - cost
        profit_total = realized + unrealized

        total_cost += cost
        total_value += current_value
        total_realized += realized
        total_buy_cost += buy_cost

        if qty > 0:
            avg_purchase_price = cost / qty
            actives.append(
                {
                    "cryptocurrency_id": crypto.id,
                    "name": crypto.name,
                    "symbol": crypto.symbol,
                    "image_url": crypto.image_url,
                    "quantity": float(qty),
                    "current_price": float(current_price),
                    "average_purchase_price": float(avg_purchase_price),
                    "profit_total": float(profit_total),
                    "total_buy_cost": float(buy_cost),
                }
            )

    unrealized_profit = total_value - total_cost
    total_profit = total_realized + unrealized_profit
    invested_base = total_buy_cost
    profit_percentage = (
        (total_profit / invested_base) * Decimal("100")
        if invested_base > 0
        else Decimal("0")
    )

    return {
        "actives": actives,
        "cost": float(total_buy_cost),
        "value": float(total_value),
        "unrealized_profit": float(unrealized_profit),
        "realized_profit": float(total_realized),
        "profit_total": float(total_profit),
        "profit_percentage": float(profit_percentage),
        "invested_base": float(invested_base),
    }


def get_portfolio_summary(portfolio_id: int):
    txns = (
        db.session.query(
            Transaction.cryptocurrency_id,
            Transaction.quantity,
            Transaction.price,
            Transaction.type,
            Transaction.transaction_date,
            Transaction.id,
        )
        .filter(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.cryptocurrency_id, Transaction.transaction_date, Transaction.id)
        .all()
    )

    if not txns:
        return _empty_summary()

    crypto_ids = sorted({txn.cryptocurrency_id for txn in txns})
    cryptos = (
        db.session.query(Cryptocurrency)
        .filter(Cryptocurrency.id.in_(crypto_ids))
        .all()
    )
    crypto_map = {crypto.id: crypto for crypto in cryptos}

    return _build_summary(txns, crypto_map)


def get_portfolio_summaries(portfolio_ids: list[int]):
    summaries = {portfolio_id: _empty_summary() for portfolio_id in portfolio_ids}
    if not portfolio_ids:
        return summaries

    txns = (
        db.session.query(
            Transaction.portfolio_id,
            Transaction.cryptocurrency_id,
            Transaction.quantity,
            Transaction.price,
            Transaction.type,
            Transaction.transaction_date,
            Transaction.id,
        )
        .filter(Transaction.portfolio_id.in_(portfolio_ids))
        .order_by(
            Transaction.portfolio_id,
            Transaction.cryptocurrency_id,
            Transaction.transaction_date,
            Transaction.id,
        )
        .all()
    )
    if not txns:
        return summaries

    crypto_ids = sorted({txn.cryptocurrency_id for txn in txns})
    cryptos = (
        db.session.query(Cryptocurrency)
        .filter(Cryptocurrency.id.in_(crypto_ids))
        .all()
    )
    crypto_map = {crypto.id: crypto for crypto in cryptos}

    txns_by_portfolio = defaultdict(list)
    for txn in txns:
        txns_by_portfolio[txn.portfolio_id].append(txn)

    for portfolio_id, portfolio_txns in txns_by_portfolio.items():
        summaries[portfolio_id] = _build_summary(portfolio_txns, crypto_map)

    return summaries
