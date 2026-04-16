from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import case, func

from extensions import db
from models import Cryptocurrency, Portfolio, Transaction
from services.portfolio_service import get_portfolio_summaries

portfolio_bp = Blueprint("portfolio", __name__)


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


@portfolio_bp.route("/portfolio")
def portfolio():
    if "user_id" not in session:
        flash("Faça login para acessar seu portfólio", "error")
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    portfolios = Portfolio.query.filter_by(user_id=user_id).all()
    cryptos = Cryptocurrency.query.all()

    portfolio_ids = [portfolio.id for portfolio in portfolios]
    summaries = get_portfolio_summaries(portfolio_ids)

    tx_by_portfolio = defaultdict(list)
    if portfolio_ids:
        tx_rows = (
            db.session.query(
                Transaction.portfolio_id,
                Transaction.id,
                Transaction.type,
                Transaction.quantity,
                Transaction.price,
                Transaction.transaction_date,
                Cryptocurrency.name,
                Cryptocurrency.symbol,
                Cryptocurrency.image_url,
            )
            .join(Cryptocurrency, Transaction.cryptocurrency_id == Cryptocurrency.id)
            .filter(Transaction.portfolio_id.in_(portfolio_ids))
            .order_by(
                Transaction.portfolio_id,
                Transaction.transaction_date.desc(),
                Transaction.id.desc(),
            )
            .all()
        )
        for row in tx_rows:
            tx_by_portfolio[row.portfolio_id].append(
                {
                    "id": row.id,
                    "type": row.type,
                    "quantity": float(row.quantity),
                    "price": float(row.price),
                    "date": str(row.transaction_date),
                    "name": row.name,
                    "symbol": row.symbol,
                    "image_url": row.image_url,
                    "total": float(row.price) * float(row.quantity),
                }
            )

    for portfolio in portfolios:
        summary = summaries.get(portfolio.id, {})
        portfolio.actives = summary.get("actives", [])
        portfolio.cost = summary.get("cost", 0.0)
        portfolio.value = summary.get("value", 0.0)
        portfolio.unrealized_profit = summary.get("unrealized_profit", 0.0)
        portfolio.realized_profit = summary.get("realized_profit", 0.0)
        portfolio.profit = summary.get("profit_total", 0.0)
        portfolio.profit_percentage = summary.get("profit_percentage", 0.0)
        portfolio.transactions = tx_by_portfolio.get(portfolio.id, [])

    return render_template("portfolio.html", portfolios=portfolios, cryptos=cryptos)


@portfolio_bp.route("/portfolio/create", methods=["POST"])
def create_portfolio():
    if "user_id" not in session:
        flash("Faça login para criar um portfólio", "error")
        return redirect(url_for("auth.login"))

    name = request.form.get("name", "Meu Portfólio").strip()
    if not name:
        name = "Meu Portfólio"

    portfolio = Portfolio(name=name, user_id=session["user_id"])
    db.session.add(portfolio)
    db.session.commit()

    flash("Portfólio criado com sucesso", "success")
    return redirect(url_for("portfolio.portfolio"))


@portfolio_bp.route("/transactions/create", methods=["POST"])
def create_transaction():
    if "user_id" not in session:
        flash("Faça login para adicionar transações", "error")
        return redirect(url_for("auth.login"))

    try:
        portfolio_id = int(request.form.get("portfolio_id"))
        cryptocurrency_id = int(request.form.get("cryptocurrency_id"))
    except (TypeError, ValueError):
        flash("Dados inválidos na transação", "error")
        return redirect(url_for("portfolio.portfolio"))

    quantity = _parse_positive_decimal(request.form.get("quantity"))
    price = _parse_positive_decimal(request.form.get("price"))
    transaction_type = (request.form.get("transaction_type") or "").strip().lower()
    transaction_date = _parse_iso_date(request.form.get("transaction_date"))

    if quantity is None or price is None or transaction_date is None:
        flash("Dados inválidos na transação", "error")
        return redirect(url_for("portfolio.portfolio"))

    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=session["user_id"]).first()
    if not portfolio:
        flash("Portfólio não encontrado", "error")
        return redirect(url_for("portfolio.portfolio"))

    crypto = Cryptocurrency.query.filter_by(id=cryptocurrency_id).first()
    if not crypto:
        flash("Criptomoeda não encontrada", "error")
        return redirect(url_for("portfolio.portfolio"))

    if transaction_type not in {"compra", "venda"}:
        flash("Tipo de transação inválido", "error")
        return redirect(url_for("portfolio.portfolio"))

    if transaction_type == "venda":
        current_qty = _current_quantity(portfolio_id, cryptocurrency_id)
        if quantity > current_qty:
            flash("Quantidade de venda superior ao disponível", "error")
            return redirect(url_for("portfolio.portfolio"))

    txn = Transaction(
        portfolio_id=portfolio_id,
        cryptocurrency_id=cryptocurrency_id,
        quantity=quantity,
        price=price,
        type=transaction_type,
        transaction_date=transaction_date,
    )
    db.session.add(txn)
    db.session.commit()

    flash("Transação adicionada com sucesso", "success")
    return redirect(url_for("portfolio.portfolio"))


@portfolio_bp.route("/portfolio/<int:portfolio_id>/delete", methods=["POST"])
def delete_portfolio(portfolio_id: int):
    if "user_id" not in session:
        flash("Faça login para excluir um portfólio", "error")
        return redirect(url_for("auth.login"))

    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=session["user_id"]).first()
    if not portfolio:
        flash("Portfólio não encontrado", "error")
        return redirect(url_for("portfolio.portfolio"))

    Transaction.query.filter_by(portfolio_id=portfolio_id).delete()
    db.session.delete(portfolio)
    db.session.commit()

    flash("Portfólio excluído com sucesso", "success")
    return redirect(url_for("portfolio.portfolio"))


@portfolio_bp.route("/portfolio/<int:portfolio_id>/asset/<int:cryptocurrency_id>/delete", methods=["POST"])
def delete_asset(portfolio_id: int, cryptocurrency_id: int):
    if "user_id" not in session:
        flash("Faça login para excluir um ativo", "error")
        return redirect(url_for("auth.login"))

    portfolio = Portfolio.query.filter_by(id=portfolio_id, user_id=session["user_id"]).first()
    if not portfolio:
        flash("Portfólio não encontrado", "error")
        return redirect(url_for("portfolio.portfolio"))

    Transaction.query.filter_by(
        portfolio_id=portfolio_id,
        cryptocurrency_id=cryptocurrency_id,
    ).delete()
    db.session.commit()

    flash("Ativo excluído (transações removidas)", "success")
    return redirect(url_for("portfolio.portfolio"))


@portfolio_bp.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
def delete_transaction(transaction_id: int):
    if "user_id" not in session:
        flash("Faça login para excluir transações", "error")
        return redirect(url_for("auth.login"))

    txn = (
        db.session.query(Transaction)
        .join(Portfolio, Transaction.portfolio_id == Portfolio.id)
        .filter(Transaction.id == transaction_id, Portfolio.user_id == session["user_id"])
        .first()
    )
    if not txn:
        flash("Transação não encontrada", "error")
        return redirect(url_for("portfolio.portfolio"))

    db.session.delete(txn)
    db.session.commit()

    flash("Transação excluída com sucesso", "success")
    return redirect(url_for("portfolio.portfolio"))


@portfolio_bp.route("/transactions/<int:transaction_id>/edit", methods=["POST"])
def edit_transaction(transaction_id: int):
    if "user_id" not in session:
        return {"error": "Não autenticado"}, 401

    txn = (
        db.session.query(Transaction)
        .join(Portfolio)
        .filter(Transaction.id == transaction_id, Portfolio.user_id == session["user_id"])
        .first()
    )
    if not txn:
        return {"error": "Transação não encontrada"}, 404

    data = request.get_json(silent=True)
    if not data:
        return {"error": "Nenhum dado recebido"}, 400

    new_type = (data.get("type", txn.type) or "").strip().lower()
    new_quantity = _parse_positive_decimal(data.get("quantity", data.get("qtd", txn.quantity)))
    new_price = _parse_positive_decimal(data.get("price", txn.price))
    new_date = _parse_iso_date(data.get("date", txn.transaction_date.strftime("%Y-%m-%d")))

    if new_type not in {"compra", "venda"}:
        return {"error": "Tipo de transação inválido"}, 400
    if new_quantity is None or new_price is None or new_date is None:
        return {"error": "Dados inválidos"}, 400

    if new_type == "venda":
        available_qty = _current_quantity(
            portfolio_id=txn.portfolio_id,
            cryptocurrency_id=txn.cryptocurrency_id,
            ignore_transaction_id=txn.id,
        )
        if new_quantity > available_qty:
            return {"error": "Quantidade de venda superior ao disponível"}, 400

    txn.type = new_type
    txn.quantity = new_quantity
    txn.price = new_price
    txn.transaction_date = new_date
    db.session.commit()

    flash("Transação editada com sucesso", "success")
    return {"success": True}
