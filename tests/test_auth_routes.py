import unittest

from flask import Blueprint, Flask

from routes.auth import auth_bp


def _create_test_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"

    portfolio_bp = Blueprint("portfolio", __name__)

    @portfolio_bp.route("/portfolio")
    def portfolio():
        return "portfolio"

    app.register_blueprint(portfolio_bp)
    app.register_blueprint(auth_bp)
    return app


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = _create_test_app()
        self.client = self.app.test_client()

    def _login_session(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_email"] = "user@example.com"

    def test_logged_in_user_is_redirected_from_login(self):
        self._login_session()

        response = self.client.get("/login")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/portfolio")

    def test_logged_in_user_is_redirected_from_register(self):
        self._login_session()

        response = self.client.get("/cadastro")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/portfolio")


if __name__ == "__main__":
    unittest.main()
