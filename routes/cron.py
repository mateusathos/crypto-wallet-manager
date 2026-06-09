from flask import Blueprint, current_app, jsonify, request

from services.price_update_service import refresh_all_cryptocurrency_prices_remote_first


cron_bp = Blueprint("cron", __name__)


def _cron_authorized() -> bool:
    expected_secret = current_app.config.get("CRON_SECRET")
    if not expected_secret:
        return True

    auth_header = request.headers.get("Authorization", "")
    return auth_header == f"Bearer {expected_secret}"


@cron_bp.route("/api/cron/update-prices", methods=["GET"])
def update_prices():
    if not _cron_authorized():
        return jsonify({"error": "unauthorized"}), 401

    result = refresh_all_cryptocurrency_prices_remote_first(
        current_app,
        vs_currency="brl",
        batch_size=100,
    )
    return jsonify(
        {
            "ok": True,
            "updated": result["updated"],
            "remote_updated": result["remote_updated"],
            "total": result["total"],
        }
    )
