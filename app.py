import secrets
from flask import Flask
from flask import abort, request, session
from dotenv import load_dotenv
from config import Config
from extensions import db, migrate
from routes.cron import cron_bp
from routes.criptomoedas import crypto_bp
from routes.homepage import homepage_bp
from routes.auth import auth_bp
from routes.portfolio import portfolio_bp
from routes.api_auth import api_auth_bp
from routes.api_cryptocurrencies import api_cryptocurrencies_bp
from routes.api_portfolios import api_portfolios_bp
from services.turso_service import init_turso_sync, push_snapshot_now, sync_now
import models  # MUITO IMPORTANTE


def _validate_csrf():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    
    if request.path.startswith("/api/"):
        return

    expected = session.get("csrf_token")
    provided = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not provided and request.is_json:
        payload = request.get_json(silent=True) or {}
        provided = payload.get("csrf_token")

    if not expected or provided != expected:
        abort(400, description="CSRF token inválido")


def create_app():
    # Carrega variáveis de ambiente do .env, se existir
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)

    init_turso_sync(app)
    db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(homepage_bp)
    app.register_blueprint(crypto_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(cron_bp)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(api_cryptocurrencies_bp)
    app.register_blueprint(api_portfolios_bp)

    write_sync_tables_by_endpoint = {
        "auth.cadastro": ["users"],
        "portfolio.create_portfolio": ["portfolios"],
        "portfolio.create_transaction": ["transactions"],
        "portfolio.edit_transaction": ["transactions"],
        "portfolio.delete_transaction": ["transactions"],
        "portfolio.delete_asset": ["transactions"],
        "portfolio.delete_portfolio": ["portfolios", "transactions"],
        "api_auth.register": ["users"],
        "api_portfolios.create_portfolio": ["portfolios"],
        "api_portfolios.create_transaction": ["transactions"],
        "api_portfolios.delete_transaction": ["transactions"],
        "api_portfolios.update_transaction": ["transactions"],
        "api_portfolios.delete_portfolio": ["portfolios", "transactions"],
        "api_portfolios.update_portfolio": ["portfolios"],
    }

    @app.before_request
    def ensure_session_and_csrf():
        sync_now(app)
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        session.permanent = True
        _validate_csrf()

    @app.after_request
    def push_sync_after_write(response):
        if not app.config.get("TURSO_PUSH_AFTER_WRITE", True):
            return response
        
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 500:
            tables = write_sync_tables_by_endpoint.get(request.endpoint)
            if tables:
                push_snapshot_now(app, table_names=tables)
            else:
                sync_now(app)
        return response

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": session.get("csrf_token", "")}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=bool(app.config.get("DEBUG", False)))
