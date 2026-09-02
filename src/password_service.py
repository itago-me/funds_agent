"""Password hashing helpers used by the user system."""

from __future__ import annotations

try:
    from pwdlib import PasswordHash
except ModuleNotFoundError as exc:  # pragma: no cover - dependency setup failure
    raise RuntimeError(
        "pwdlib is required for password hashing. "
        "Run: pip install 'pwdlib[argon2]'"
    ) from exc


_password_hash = PasswordHash.recommended()


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(character.isalpha() for character in password):
        raise ValueError("Password must include at least one letter.")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must include at least one number.")


def hash_password(password: str) -> str:
    """Return a salted Argon2id password hash."""
    if not password:
        raise ValueError("Password must not be empty")
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches a stored hash."""
    if not password or not password_hash:
        return False
    return _password_hash.verify(password, password_hash)
