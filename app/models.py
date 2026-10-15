"""Модели данных и схемы таблиц.

В проекте два независимых хранилища пользователей, каждое в своём файле SQLite:

- HTTP API (``API_DB``) — у пользователя есть только имя;
- профили (``USERS_DB``) — имя, теги и хеш пароля.
"""

from __future__ import annotations

from typing import TypedDict


class User(TypedDict):
    """Пользователь HTTP API."""

    id: int
    name: str


class UserProfile(TypedDict):
    """Профиль пользователя. Хеш пароля наружу не отдаётся."""

    id: int
    name: str
    tags: list[str]


API_USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
"""

PROFILES_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    tags          TEXT NOT NULL DEFAULT '[]',
    password_hash TEXT
)
"""
