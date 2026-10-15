"""Хранилище профилей: пользователи с тегами и паролями."""

from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from ..config import PROFILES_DB_PATH
from ..db import connect
from ..models import PROFILES_SCHEMA, UserProfile
from ..utils.passwords import check_password, hash_password
from ..utils.validation import is_valid_name

NEW_USER_TAG = "new"


def add_user(
    name: str,
    tags: Iterable[str] | None = None,
    *,
    db_path: str | Path = PROFILES_DB_PATH,
) -> int:
    """Добавляет пользователя и возвращает его id.

    К тегам добавляется метка ``"new"``; переданный список не изменяется.
    """
    if not is_valid_name(name):
        raise ValueError("name must be a non-empty string")

    all_tags = list(tags or ())
    if NEW_USER_TAG not in all_tags:
        all_tags.append(NEW_USER_TAG)

    with closing(connect(db_path, PROFILES_SCHEMA)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO users (name, tags) VALUES (?, ?)",
            (name, json.dumps(all_tags)),
        )
        return cur.lastrowid


def get_user_by_name(name: str, *, db_path: str | Path = PROFILES_DB_PATH) -> UserProfile | None:
    """Возвращает пользователя с данным именем или ``None``, если его нет.

    Если имя не уникально, возвращается самый ранний пользователь.
    """
    with closing(connect(db_path, PROFILES_SCHEMA)) as conn:
        row = conn.execute(
            "SELECT id, name, tags FROM users WHERE name = ? ORDER BY id LIMIT 1",
            (name,),
        ).fetchone()

    if row is None:
        return None
    uid, uname, tags_json = row
    return {"id": uid, "name": uname, "tags": json.loads(tags_json)}


def store_password(user_id: int, password: str, *, db_path: str | Path = PROFILES_DB_PATH) -> None:
    """Сохраняет хеш пароля пользователя."""
    if not password:
        raise ValueError("password must not be empty")

    password_hash = hash_password(password)
    with closing(connect(db_path, PROFILES_SCHEMA)) as conn, conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"user {user_id} not found")


def verify_password(user_id: int, password: str, *, db_path: str | Path = PROFILES_DB_PATH) -> bool:
    """Проверяет пароль пользователя. ``False``, если пользователя или пароля нет."""
    with closing(connect(db_path, PROFILES_SCHEMA)) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    if row is None or row[0] is None:
        return False
    return check_password(password, row[0])
