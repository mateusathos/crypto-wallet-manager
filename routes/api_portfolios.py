from collections import defaultdict

from flask import Blueprint, jsonify, session
from sqlalchemy import desc

from extensions import db
from models import Cryptocurrency, Portfolio, Transaction
from routes.api_helpers import login_required_json
from services.portfolio_service import get_portfolio_summaries


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