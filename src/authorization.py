"""Role definitions and validation for application authorization."""

from __future__ import annotations


ROLE_USER = "user"
ROLE_ADMIN = "admin"
SUPPORTED_ROLES = {ROLE_USER, ROLE_ADMIN}


def validate_role(role: str) -> str:
    normalized = str(role).strip().lower()
    if normalized not in SUPPORTED_ROLES:
        raise ValueError(f"Unsupported user role: {role}")
    return normalized
