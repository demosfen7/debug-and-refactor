"""Хеширование паролей: scrypt со случайной солью.

Формат хеша: ``scrypt$n$r$p$<соль hex>$<хеш hex>`` — параметры хранятся
вместе с хешем, поэтому их можно усилить, не ломая старые записи.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# Параметры scrypt: n=2**14, r=8, p=1 — минимум по рекомендации OWASP.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored_hash: str) -> bool:
    """Сравнивает пароль с хешем за постоянное время."""
    _, n, r, p, salt_hex, digest_hex = stored_hash.split("$")
    candidate = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
    )
    return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
