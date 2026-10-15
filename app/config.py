"""Настройки из переменных окружения."""

from __future__ import annotations

import os
from pathlib import Path


def api_database() -> str:
    """Путь к БД HTTP API. Читается при создании приложения."""
    return os.environ.get("API_DB", "test.db")


# Путь к БД профилей по умолчанию. Читается при импорте; в функциях
# хранилища его можно переопределить аргументом db_path.
PROFILES_DB_PATH = Path(os.environ.get("USERS_DB", "users.db"))
