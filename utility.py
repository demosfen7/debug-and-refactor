"""Утилиты для работы с пользователями: хранение в SQLite, пароли, список активных."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from collections import deque
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import TypedDict

DB_PATH = Path(os.environ.get("USERS_DB", "users.db"))

NEW_USER_TAG = "new"
MAX_ACTIVE_USERS = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    tags          TEXT NOT NULL DEFAULT '[]',
    password_hash TEXT
)
"""

# Параметры scrypt: n=2**14, r=8, p=1 — минимум по рекомендации OWASP.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_SALT_BYTES = 16


class User(TypedDict):
    id: int
    name: str
    tags: list[str]


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    return conn


def add_user(
    name: str,
    tags: Iterable[str] | None = None,
    *,
    db_path: str | Path = DB_PATH,
) -> int:
    """Добавляет пользователя и возвращает его id.

    К тегам добавляется метка ``"new"``; переданный список не изменяется.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")

    all_tags = list(tags or ())
    if NEW_USER_TAG not in all_tags:
        all_tags.append(NEW_USER_TAG)

    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO users (name, tags) VALUES (?, ?)",
            (name, json.dumps(all_tags)),
        )
        return cur.lastrowid


def get_user_by_name(name: str, *, db_path: str | Path = DB_PATH) -> User | None:
    """Возвращает пользователя с данным именем или ``None``, если его нет.

    Если имя не уникально, возвращается самый ранний пользователь.
    """
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT id, name, tags FROM users WHERE name = ? ORDER BY id LIMIT 1",
            (name,),
        ).fetchone()

    if row is None:
        return None
    uid, uname, tags_json = row
    return {"id": uid, "name": uname, "tags": json.loads(tags_json)}


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def store_password(user_id: int, password: str, *, db_path: str | Path = DB_PATH) -> None:
    """Сохраняет хеш пароля пользователя (scrypt с солью)."""
    if not password:
        raise ValueError("password must not be empty")

    password_hash = _hash_password(password)
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"user {user_id} not found")


def verify_password(user_id: int, password: str, *, db_path: str | Path = DB_PATH) -> bool:
    """Проверяет пароль пользователя. ``False``, если пользователя или пароля нет."""
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    if row is None or row[0] is None:
        return False
    _, n, r, p, salt_hex, digest_hex = row[0].split("$")
    candidate = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
    )
    return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))


# Последние MAX_ACTIVE_USERS активных пользователей, самый свежий — в конце.
_active_users: deque[int] = deque(maxlen=MAX_ACTIVE_USERS)
_active_lock = threading.Lock()


def set_active(user_id: int) -> None:
    """Отмечает пользователя активным; самые давние вытесняются из списка."""
    with _active_lock:
        if user_id in _active_users:
            _active_users.remove(user_id)
        _active_users.append(user_id)


def get_active_users() -> list[int]:
    """Возвращает копию списка активных пользователей (от давних к свежим)."""
    with _active_lock:
        return list(_active_users)
