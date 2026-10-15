"""HTTP-маршруты приложения."""

from flask import Flask

from .users import bp as users_bp


def register_routes(app: Flask) -> None:
    app.register_blueprint(users_bp)
