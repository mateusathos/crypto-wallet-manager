from collections import defaultdict

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import case, desc, func
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from extensions import db
from models import Cryptocurrency, Portfolio, Transaction
from routes.api_helpers import api_error, login_required_json
from services.portfolio_icons import normalize_portfolio_icon
from services.portfolio_service import get_portfolio_summaries
from services.turso_service import (
    create_remote_portfolio,
    create_remote_transaction,
    delete_remote_portfolio,
    delete_remote_transaction,
    update_remote_portfolio,
    update_remote_transaction,
)


api_portfolios_bp = Blueprint(
    "api_portfolios",
    __name__,
    url_prefix="/api/portfolios",
)


def _transaction_payload(row):
    return {
        "id": row.id,
        "type": row.type,
        "quantity": float(row.quantity),
        "price": float(row.price),
        "date": row.transaction_date.isoformat(),
        "cryptocurrency": {
            "id": row.cryptocurrency_id,
            "name": row.crypto_name,
            "symbol": row.crypto_symbol,
            "image_url": row.crypto_image_url,
        },
        "total": float(row.price) * float(row.quantity),
    }


def _portfolio_payload(portfolio: Portfolio, summary: dict, transactions: list):
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "icon": portfolio.icon,
        "summary": {
            "actives": summary.get("actives", []),
            "cost": summary.get("cost", 0.0),
            "value": summary.get("value", 0.0),
            "unrealized_profit": summary.get("unrealized_profit", 0.0),
            "realized_profit": summary.get("realized_profit", 0.0),
            "profit_total": summary.get("profit_total", 0.0),
            "profit_percentage": summary.get("profit_percentage", 0.0),
            "invested_base": summary.get("invested_base", 0.0),
        },
        "transactions": transactions,
    }


def _parse_positive_decimal(raw_value):
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return None

    if value <= 0:
        return None

    return value


def _parse_iso_date(raw_value):
    try:
        return datetime.strptime(str(raw_value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    

def _current_quantity(
    portfolio_id: int,
    cryptocurrency_id: int,
    ignore_transaction_id: Optional[int] = None,
):
    quantity_expr = func.sum(
        case(
            (Transaction.type == "compra", Transaction.quantity),
            (Transaction.type == "venda", -Transaction.quantity),
            else_=0,
        )
    )

    query = db.session.query(quantity_expr).filter(
        Transaction.portfolio_id == portfolio_id,
        Transaction.cryptocurrency_id == cryptocurrency_id,
    )

    if ignore_transaction_id is not None:
        query = query.filter(Transaction.id != ignore_transaction_id)

    return Decimal(str(query.scalar() or 0))


@api_portfolios_bp.get("")
@login_required_json
def list_portfolios():
    user_id = session["user_id"]

    portfolios = Portfolio.query.filter_by(user_id=user_id).all()
    portfolio_ids = [portfolio.id for portfolio in portfolios]

    summaries = get_portfolio_summaries(portfolio_ids)

    transactions_by_portfolio = defaultdict(list)

    if portfolio_ids:
        rows = (
            db.session.query(
                Transaction.id,
                Transaction.portfolio_id,
                Transaction.cryptocurrency_id,
                Transaction.type,
                Transaction.quantity,
                Transaction.price,
                Transaction.transaction_date,
                Cryptocurrency.name.label("crypto_name"),
                Cryptocurrency.symbol.label("crypto_symbol"),
                Cryptocurrency.image_url.label("crypto_image_url"),
            )
            .join(Cryptocurrency, Transaction.cryptocurrency_id == Cryptocurrency.id)
            .filter(Transaction.portfolio_id.in_(portfolio_ids))
            .order_by(
                Transaction.portfolio_id,
                desc(Transaction.transaction_date),
                desc(Transaction.id),
            )
            .all()
        )

        for row in rows:
            transactions_by_portfolio[row.portfolio_id].append(
                _transaction_payload(row)
            )

    return jsonify({
        "portfolios": [
            _portfolio_payload(
                portfolio=portfolio,
                summary=summaries.get(portfolio.id, {}),
                transactions=transactions_by_portfolio.get(portfolio.id, []),
            )
            for portfolio in portfolios
        ]
    })


@api_portfolios_bp.post("")
@login_required_json
def create_portfolio():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "Meu Portfólio").strip()

    if not name:
        name = "Meu Portfólio"

    portfolio = Portfolio(
        name=name,
        icon=normalize_portfolio_icon(data.get("icon")),
        user_id=session["user_id"],
    )

    db.session.add(portfolio)
    db.session.flush()
    create_remote_portfolio(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        portfolio,
    )
    db.session.commit()

    summary = {
        "actives": [],
        "cost": 0.0,
        "value": 0.0,
        "unrealized_profit": 0.0,
        "realized_profit": 0.0,
        "profit_total": 0.0,
        "profit_percentage": 0.0,
        "invested_base": 0.0,
    }

    return jsonify({
        "portfolio": _portfolio_payload(
            portfolio=portfolio,
            summary=summary,
            transactions=[],
        )
    }), 201


@api_portfolios_bp.post("/transactions")
@login_required_json
def create_transaction():
    data = request.get_json(silent=True) or {}

    try:
        portfolio_id = int(data.get("portfolio_id"))
        cryptocurrency_id = int(data.get("cryptocurrency_id"))
    except (TypeError, ValueError):
        return api_error("Portfólio ou criptomoeda inválidos.")
    
    transaction_type = (data.get("type") or data.get("transaction_type") or "").strip().lower()
    quantity = _parse_positive_decimal(data.get("quantity"))
    price = _parse_positive_decimal(data.get("price"))
    transaction_date = _parse_iso_date(data.get("date") or data.get("transaction_date"))

    if transaction_type not in {"compra", "venda"}:
        return api_error("Tipo de transação inválido.")

    if quantity is None or price is None or transaction_date is None:
        return api_error("Dados inválidos na transação.")
    
    portfolio = Portfolio.query.filter_by(
        id=portfolio_id,
        user_id=session["user_id"],
    ).first()

    if not portfolio:
        return api_error("Portfólio não encontrado.", 404)
    
    crypto = Cryptocurrency.query.filter_by(id=cryptocurrency_id).first()

    if not crypto:
        return api_error("Criptomoeda não encontrada.", 404)
    
    if transaction_type == "venda":
        current_qty = _current_quantity(
            portfolio_id=portfolio.id,
            cryptocurrency_id=crypto.id,
        )

        if quantity > current_qty:
            return api_error("Quantidade de venda superior ao disponível.")

    transaction = Transaction(
        portfolio_id=portfolio.id,
        cryptocurrency_id=crypto.id,
        quantity=quantity,
        price=price,
        type=transaction_type,
        transaction_date=transaction_date,
    )

    db.session.add(transaction)
    db.session.flush()
    create_remote_transaction(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        transaction,
    )
    db.session.commit()

    return jsonify({
        "transaction": {
            "id": transaction.id,
            "portfolio_id": transaction.portfolio_id,
            "cryptocurrency_id": transaction.cryptocurrency_id,
            "type": transaction.type,
            "quantity": float(transaction.quantity),
            "price": float(transaction.price),
            "date": transaction.transaction_date.isoformat(),
            "total": float(transaction.quantity) * float(transaction.price),
        }
    }), 201


@api_portfolios_bp.delete("/transactions/<int:transaction_id>")
@login_required_json
def delete_transaction(transaction_id: int):
    transaction = (
        db.session.query(Transaction)
        .join(Portfolio, Transaction.portfolio_id == Portfolio.id)
        .filter(
            Transaction.id == transaction_id,
            Portfolio.user_id == session["user_id"],
        )
        .first()
    )

    if not transaction:
        return api_error("Transação não encontrada.", 404)

    delete_remote_transaction(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        transaction_id=transaction_id,
        user_id=session["user_id"],
    )
    db.session.delete(transaction)
    db.session.commit()

    return jsonify({"success": True})


@api_portfolios_bp.patch("/transactions/<int:transaction_id>")
@login_required_json
def update_transaction(transaction_id: int):
    transaction = (
        db.session.query(Transaction)
        .join(Portfolio, Transaction.portfolio_id == Portfolio.id)
        .filter(
            Transaction.id == transaction_id,
            Portfolio.user_id == session["user_id"],
        )
        .first()
    )

    if not transaction:
        return api_error("Transação não encontrada.", 404)

    data = request.get_json(silent=True) or {}

    transaction_type = (
        data.get("type")
        or data.get("transaction_type")
        or transaction.type
    ).strip().lower()

    quantity = _parse_positive_decimal(
        data.get("quantity", transaction.quantity)
    )

    price = _parse_positive_decimal(
        data.get("price", transaction.price)
    )

    transaction_date = _parse_iso_date(
        data.get(
            "date",
            transaction.transaction_date.isoformat(),
        )
    )

    if transaction_type not in {"compra", "venda"}:
        return api_error("Tipo de transação inválido.")

    if quantity is None or price is None or transaction_date is None:
        return api_error("Dados inválidos na transação.")

    crypto_id = data.get("cryptocurrency_id")
    target_crypto_id = transaction.cryptocurrency_id

    if crypto_id is not None:
        try:
            crypto_id = int(crypto_id)
        except (TypeError, ValueError):
            return api_error("Criptomoeda inválida.")

        crypto = Cryptocurrency.query.filter_by(id=crypto_id).first()

        if not crypto:
            return api_error("Criptomoeda não encontrada.", 404)

        transaction.cryptocurrency_id = crypto.id

    has_changes = (
        transaction_type != transaction.type
        or quantity != transaction.quantity
        or price != transaction.price
        or transaction_date != transaction.transaction_date
        or (
            data.get("cryptocurrency_id") is not None
            and int(data.get("cryptocurrency_id")) != transaction.cryptocurrency_id
        )
    )

    if not has_changes:
        return api_error("Nenhuma alteração informada.")

    if transaction_type == "venda":
        available_qty = _current_quantity(
            portfolio_id=transaction.portfolio_id,
            cryptocurrency_id=target_crypto_id,
            ignore_transaction_id=transaction.id,
        )

        if quantity > available_qty:
            return api_error("Quantidade de venda superior ao disponível.")

    transaction.cryptocurrency_id = target_crypto_id
    transaction.type = transaction_type
    transaction.quantity = quantity
    transaction.price = price
    transaction.transaction_date = transaction_date
    update_remote_transaction(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        transaction,
        user_id=session["user_id"],
    )

    db.session.commit()

    return jsonify({
        "transaction": {
            "id": transaction.id,
            "portfolio_id": transaction.portfolio_id,
            "cryptocurrency_id": transaction.cryptocurrency_id,
            "type": transaction.type,
            "quantity": float(transaction.quantity),
            "price": float(transaction.price),
            "date": transaction.transaction_date.isoformat(),
            "total": float(transaction.quantity) * float(transaction.price),
        }
    })


@api_portfolios_bp.delete("/<int:portfolio_id>")
@login_required_json
def delete_portfolio(portfolio_id: int):
    portfolio = Portfolio.query.filter_by(
        id=portfolio_id,
        user_id=session["user_id"],
    ).first()

    if not portfolio:
        return api_error("Portfólio não encontrado.", 404)

    delete_remote_portfolio(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        portfolio_id=portfolio.id,
        user_id=session["user_id"],
    )
    Transaction.query.filter_by(portfolio_id=portfolio.id).delete()
    db.session.delete(portfolio)
    db.session.commit()

    return jsonify({"success": True})


@api_portfolios_bp.patch("/<int:portfolio_id>")
@login_required_json
def update_portfolio(portfolio_id: int):
    portfolio = Portfolio.query.filter_by(
        id=portfolio_id,
        user_id=session["user_id"],
    ).first()

    if not portfolio:
        return api_error("Portfólio não encontrado.", 404)

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or portfolio.name).strip()
    icon = normalize_portfolio_icon(data.get("icon", portfolio.icon))

    if not name:
        return api_error("Nome do portfólio é obrigatório.")

    if name == portfolio.name and icon == portfolio.icon:
        return api_error("Nenhuma alteração informada.")

    portfolio.name = name
    portfolio.icon = icon
    update_remote_portfolio(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        portfolio,
    )
    db.session.commit()

    summary = get_portfolio_summaries([portfolio.id]).get(portfolio.id, {})

    return jsonify({
        "portfolio": _portfolio_payload(
            portfolio=portfolio,
            summary=summary,
            transactions=[],
        )
    })
