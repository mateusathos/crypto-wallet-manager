from functools import wraps

from flask import jsonify, session


def api_error(message: str, status_code: int = 400):
    response = jsonify({"error": message})
    return response, status_code


def login_required_json(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return api_error("Não autenticado", 401)
        return view(*args, **kwargs)

    return wrapped

