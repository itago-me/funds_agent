"""User authentication services and FastAPI dependency helpers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Annotated, Any, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.auth_session import SESSION_COOKIE_NAME, read_session_user_id
from src.authorization import ROLE_ADMIN, ROLE_USER
from src.db import get_session_factory
from src.models import User
from src.password_service import (
    hash_password,
    validate_password_policy,
    verify_password,
)


SessionFactory = Callable[[], AbstractContextManager]
SessionUserIdLoader = Callable[[str | None], int | None]
CurrentUserLoader = Callable[[str | None], User | None]


class UsernameAlreadyExistsError(ValueError):
    """Raised when a registration request uses an existing username."""


def authenticate_user(
    username: str,
    password: str,
    *,
    session_factory: SessionFactory | None = None,
) -> User | None:
    normalized_username = username.strip()
    if not normalized_username or not password:
        return None

    factory = session_factory or get_session_factory()
    session = factory()
    try:
        user = session.execute(
            select(User).where(User.username == normalized_username)
        ).scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    finally:
        session.close()


def register_user(
    username: str,
    password: str,
    *,
    session_factory: SessionFactory | None = None,
) -> User:
    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Username must not be empty.")
    if not password:
        raise ValueError("Password must not be empty.")

    validate_password_policy(password)

    factory = session_factory or get_session_factory()
    session = factory()
    try:
        existing_user = session.execute(
            select(User).where(User.username == normalized_username)
        ).scalar_one_or_none()
        if existing_user is not None:
            raise UsernameAlreadyExistsError("Username already exists.")

        user = User(
            username=normalized_username,
            password_hash=hash_password(password),
            role=ROLE_USER,
            is_active=True,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise UsernameAlreadyExistsError("Username already exists.") from exc
        session.refresh(user)
        return user
    finally:
        session.close()


def load_current_user(
    session_id: str | None,
    *,
    session_user_id_loader: SessionUserIdLoader = read_session_user_id,
    session_factory: SessionFactory | None = None,
) -> User | None:
    user_id = session_user_id_loader(session_id)
    if user_id is None:
        return None

    factory = session_factory or get_session_factory()
    session = factory()
    try:
        return session.execute(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        ).scalar_one_or_none()
    finally:
        session.close()


def public_user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def get_current_user_from_request(
    request: Request,
    *,
    current_user_loader: CurrentUserLoader = load_current_user,
) -> User | None:
    return current_user_loader(request.cookies.get(SESSION_COOKIE_NAME))


def require_authenticated_user(
    request: Request,
) -> User:
    """Return the current active user or reject the request with HTTP 401."""
    user = get_current_user_from_request(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def require_admin_user(request: Request) -> User:
    """Return the current admin or reject the request with HTTP 401/403."""
    user = require_authenticated_user(request)
    return authorize_admin_user(user)


def authorize_admin_user(user: User) -> User:
    """Return an admin user or reject a normal user with HTTP 403."""
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required.",
        )
    return user


AuthenticatedUser = Annotated[User, Depends(require_authenticated_user)]
AdminUser = Annotated[User, Depends(require_admin_user)]
