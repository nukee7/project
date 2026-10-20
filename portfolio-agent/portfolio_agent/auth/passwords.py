"""Password hashing and verification using bcrypt."""

from __future__ import annotations

import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    """Hash a password with a random salt using SHA-256.

    Uses hashlib (stdlib) instead of bcrypt to avoid native dependencies.
    For production, switch to bcrypt or argon2.
    """
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        stored_key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(new_key, stored_key)
    except (ValueError, AttributeError):
        return False
