"""Salted Argon2id password hashing and verification."""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash the full password with a new random salt on every call."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return False for a mismatch or an unrecognized stored hash."""
    try:
        return password_hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError, TypeError):
        return False
