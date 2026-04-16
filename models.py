from extensions import db
from sqlalchemy import Enum

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Cryptocurrency(db.Model):
    __tablename__ = "cryptocurrencies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    coingecko_id = db.Column(db.String(50), unique=True, nullable=False)
    image_url = db.Column(db.String(255))

    # Dados dinâmicos
    current_price = db.Column(db.Numeric(20, 8), nullable=True)
    current_marketcap = db.Column(db.Numeric(25, 2), nullable=True)
    price_change_percentage_24h = db.Column(db.Numeric(10, 4), nullable=True)
    last_updated = db.Column(db.DateTime, nullable=True)


class Portfolio(db.Model):
    __tablename__ = "portfolios"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), default="Meu Portfólio")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(
        db.Integer, db.ForeignKey("portfolios.id"), nullable=False
    )
    cryptocurrency_id = db.Column(
        db.Integer, db.ForeignKey("cryptocurrencies.id"), nullable=False
    )
    quantity = db.Column(db.Numeric(18, 8), nullable=False)
    price = db.Column(db.Numeric(18, 8), nullable=False)
    fee = db.Column(db.Numeric(18, 8), nullable=False, default=0)
    type = db.Column(
        Enum('venda', 'compra', name='transaction_type'), nullable=False
    )
    transaction_date = db.Column(db.Date, nullable=False)
