"""Подключения к SQLite."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from flask import Flask, current_app, g

from .models import API_USERS_SCHEMA


def connect(path: str | Path, schema: str) -> sqlite3.Connection:
    """Открывает БД и создаёт таблицу по схеме, если её ещё нет."""
    conn = sqlite3.connect(path)
    conn.execute(schema)
    return conn


def get_db() -> sqlite3.Connection:
    """Соединение с БД HTTP API, своё на каждый запрос."""
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


def init_app(app: Flask) -> None:
    """Готовит БД HTTP API и закрывает соединения после каждого запроса."""
    with closing(sqlite3.connect(app.config["DATABASE"])) as conn, conn:
        conn.execute("PRAGMA journal_mode = WAL")  # сохраняется в файле БД
        conn.execute(API_USERS_SCHEMA)
    app.teardown_appcontext(close_db)
