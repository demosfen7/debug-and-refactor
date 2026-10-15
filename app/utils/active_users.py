"""Список недавно активных пользователей в памяти процесса."""

from __future__ import annotations

import threading
from collections import deque

MAX_ACTIVE_USERS = 5


class ActiveUsers:
    """Последние ``limit`` активных пользователей без повторов, потокобезопасно."""

    def __init__(self, limit: int = MAX_ACTIVE_USERS) -> None:
        self._items: deque[int] = deque(maxlen=limit)
        self._lock = threading.Lock()

    def mark(self, user_id: int) -> None:
        """Отмечает пользователя активным; самые давние вытесняются."""
        with self._lock:
            if user_id in self._items:
                self._items.remove(user_id)
            self._items.append(user_id)

    def snapshot(self) -> list[int]:
        """Копия списка, от давних к свежим."""
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_default = ActiveUsers()


def set_active(user_id: int) -> None:
    """Отмечает пользователя активным в общем списке процесса."""
    _default.mark(user_id)


def get_active_users() -> list[int]:
    """Общий список активных пользователей процесса."""
    return _default.snapshot()
