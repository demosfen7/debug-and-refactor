"""HTTP API для пользователей.

Запуск: ``flask --app api run`` (Flask сам найдёт фабрику ``create_app``).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, current_app, g, jsonify, request, url_for

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
"""


def get_db() -> sqlite3.Connection:
    """Соединение с БД, своё на каждый запрос."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        # В WAL коммит без fsync безопасен для целостности и не тормозит
        # очередь писателей при параллельных запросах.
        g.db.execute("PRAGMA synchronous = NORMAL")
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database: str) -> None:
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute("PRAGMA journal_mode = WAL")  # сохраняется в файле БД
        conn.execute(_SCHEMA)


def create_app(database: str | Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = str(database or os.environ.get("API_DB", "test.db"))
    app.teardown_appcontext(close_db)
    init_db(app.config["DATABASE"])

    @app.post("/adduser")
    def add_user():
        data = request.get_json(silent=True)
        name = data.get("name") if isinstance(data, dict) else None
        if not isinstance(name, str) or not name.strip():
            return jsonify(error="field 'name' must be a non-empty string"), 400

        db = get_db()
        with db:
            uid = db.execute("INSERT INTO users (name) VALUES (?)", (name,)).lastrowid
        return (
            jsonify(id=uid, name=name),
            201,
            {"Location": url_for("get_user", uid=uid)},
        )

    @app.get("/user/<int:uid>")
    def get_user(uid: int):
        row = get_db().execute(
            "SELECT id, name FROM users WHERE id = ?", (uid,)
        ).fetchone()
        if row is None:
            return jsonify(error="user not found"), 404
        return jsonify(id=row[0], name=row[1])

    return app


if __name__ == "__main__":
    create_app().run()
