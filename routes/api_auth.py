from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User
from routes.api_helpers import api_error, login_required_json
from routes.auth import _normalize_email


api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")


def _user_payload(user: User):
    return {
        "id": user.id,
        "email": user.email,
    }


@api_auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    email = _normalize_email(data.get("email"))
    password = data.get("password") or data.get("senha") or ""
    confirm_password = data.get("confirm_password") or data.get("confirmar") or password

    if not email or not password:
        return api_error("Preencha email e senha.")
    
    if password != confirm_password:
        return api_error("As senhas não coincidem.")

    if User.query.filter_by(email=email).first():
        return api_error("Este email já está cadastrado.", 409)

    user = User(email=email, password_hash=generate_password_hash(password))
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return api_error("Este email já está cadastrado.", 409)
    
    session["user_id"] = user.id
    session["user_email"] = user.email

    return jsonify({"user": _user_payload(user)}), 201


@api_auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    email = _normalize_email(data.get("email"))
    password = data.get("password") or data.get("senha") or ""

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return api_error("Email ou senha inválidos.", 401)
    
    session["user_id"] = user.id
    session["user_email"] = user.email

    return jsonify({"user": _user_payload(user)})


@api_auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})


@api_auth_bp.get("/me")
@login_required_json
def me():
    user = User.query.get(session["user_id"])

    if not user:
        session.clear()
        return api_error("Usuário não encontrado.", 404)

    return jsonify({"user": _user_payload(user)})
