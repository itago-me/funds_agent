"""Database operations used by the administrator user-management API."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Callable

from sqlalchemy import func, select

from src.auth_service import public_user_payload
from src.authorization import ROLE_ADMIN, ROLE_USER, validate_role
from src.db import get_session_factory
from src.models import User
from src.password_service import hash_password


SessionFactory = Callable[[], AbstractContextManager]
MIN_RESET_PASSWORD_LENGTH = 8


class UserAdminError(ValueError):
    """Base error for administrator user-management operations."""


class UserNotFoundError(UserAdminError):
    pass


class LastAdminProtectionError(UserAdminError):
    pass


class SelfModificationError(UserAdminError):
    pass


def _factory(session_factory: SessionFactory | None) -> SessionFactory:
    return session_factory or get_session_factory()


def list_users(
    *,
    session_factory: SessionFactory | None = None,
) -> list[dict[str, object]]:
    with _factory(session_factory)() as session:
        users = session.execute(select(User).order_by(User.id.asc())).scalars().all()
        return [public_user_payload(user) for user in users]


def _load_user(session: Any, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError(f"User not found: {user_id}")
    return user


def _count_active_admins(session: Any) -> int:
    count = session.execute(
        select(func.count())
        .select_from(User)
        .where(User.role == ROLE_ADMIN, User.is_active.is_(True))
    ).scalar_one()
    return int(count)


def update_user(
    user_id: int,
    *,
    current_admin_id: int,
    role: str | None = None,
    is_active: bool | None = None,
    session_factory: SessionFactory | None = None,
) -> User:
    if role is None and is_active is None:
        raise ValueError("At least one user field must be provided.")
    normalized_role = validate_role(role) if role is not None else None

    with _factory(session_factory)() as session:
        user = _load_user(session, user_id)
        next_role = normalized_role if normalized_role is not None else user.role
        next_active = is_active if is_active is not None else user.is_active

        changing_own_privilege = (
            user.id == current_admin_id
            and (next_role != user.role or next_active is False)
        )
        if changing_own_privilege:
            raise SelfModificationError(
                "Administrators cannot change their own role or disable themselves."
            )

        removes_active_admin = (
            user.role == ROLE_ADMIN
            and user.is_active
            and (next_role != ROLE_ADMIN or next_active is False)
        )
        if removes_active_admin and _count_active_admins(session) <= 1:
            raise LastAdminProtectionError(
                "At least one active administrator must remain."
            )

        user.role = next_role
        user.is_active = next_active
        session.commit()
        session.refresh(user)
        return user


def reset_user_password(
    user_id: int,
    password: str,
    *,
    session_factory: SessionFactory | None = None,
) -> User:
    if len(password) < MIN_RESET_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_RESET_PASSWORD_LENGTH} characters."
        )

    with _factory(session_factory)() as session:
        user = _load_user(session, user_id)
        user.password_hash = hash_password(password)
        session.commit()
        session.refresh(user)
        return user
