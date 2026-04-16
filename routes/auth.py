from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)


def _normalize_email(raw_email: str) -> str:
    return (raw_email or "").strip().lower()


@auth_bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        email = _normalize_email(request.form.get("email"))
        senha = request.form.get("senha") or ""
        confirmar = request.form.get("confirmar") or ""

        if not email or not senha:
            flash("Preencha email e senha.", "error")
            return redirect(url_for("auth.cadastro"))

        if senha != confirmar:
            flash("As senhas não coincidem.", "error")
            return redirect(url_for("auth.cadastro"))

        usuario_existente = User.query.filter_by(email=email).first()
        if usuario_existente:
            flash("Este email já está cadastrado.", "error")
            return redirect(url_for("auth.cadastro"))

        user = User(email=email, password_hash=generate_password_hash(senha))
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Este email já está cadastrado.", "error")
            return redirect(url_for("auth.cadastro"))

        session["user_id"] = user.id
        session["user_email"] = user.email
        return redirect(url_for("homepage.homepage"))

    return render_template("cadastro.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = _normalize_email(request.form.get("email"))
        senha = request.form.get("senha") or ""

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email não cadastrado.", "error")
            return redirect(url_for("auth.login"))
        if not check_password_hash(user.password_hash, senha):
            flash("Senha incorreta.", "error")
            return redirect(url_for("auth.login"))

        session["user_id"] = user.id
        session["user_email"] = user.email
        return redirect(url_for("homepage.homepage"))
    return render_template("login.html")


@auth_bp.route("/sair", methods=["POST"])
def sair():
    session.clear()
    flash("Sessão encerrada.")
    return redirect(url_for("auth.login"))
