"""Проверка входных данных."""

from __future__ import annotations


def is_valid_name(value: object) -> bool:
    """Имя — непустая строка, не из одних пробелов."""
    return isinstance(value, str) and bool(value.strip())


def name_from_payload(payload: object) -> str | None:
    """Достаёт корректное поле ``name`` из разобранного JSON или возвращает ``None``."""
    name = payload.get("name") if isinstance(payload, dict) else None
    return name if is_valid_name(name) else None
