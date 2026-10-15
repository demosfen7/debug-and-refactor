"""HTTP API пользователей и хранилище профилей.

Запуск сервера: ``flask --app app run`` или ``python -m app``.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask

from . import config, db
from .routes import register_routes


def create_app(database: str | Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = str(database or config.api_database())
    db.init_app(app)
    register_routes(app)
    return app
