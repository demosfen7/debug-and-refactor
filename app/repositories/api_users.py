"""Хранилище пользователей HTTP API."""

from __future__ import annotations

import sqlite3

from ..models import User


def insert_user(conn: sqlite3.Connection, name: str) -> User:
    with conn:
        uid = conn.execute("INSERT INTO users (name) VALUES (?)", (name,)).lastrowid
    return {"id": uid, "name": name}


def find_user(conn: sqlite3.Connection, uid: int) -> User | None:
    row = conn.execute("SELECT id, name FROM users WHERE id = ?", (uid,)).fetchone()
    if row is None:
        return None
    return {"id": row[0], "name": row[1]}
