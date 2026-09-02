"""Database-backed audit event storage."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any, Callable

from src.db import get_session_factory
from src.models import AuditLog


SessionFactory = Callable[[], AbstractContextManager]
SENSITIVE_DETAIL_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
}


def _factory(session_factory: SessionFactory | None) -> SessionFactory:
    return session_factory or get_session_factory()


def _sanitize_details(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_details(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_DETAIL_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_details(item) for item in value]
    return value


def _record_from_model(event: AuditLog) -> dict[str, object]:
    return {
        "audit_id": event.id,
        "actor_user_id": event.actor_user_id,
        "target_user_id": event.target_user_id,
        "action": event.action,
        "success": event.success,
        "details": event.details,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "created_at": (
            event.created_at.isoformat(timespec="seconds")
            if isinstance(event.created_at, datetime)
            else event.created_at
        ),
    }


def record_audit_event(
    *,
    action: str,
    success: bool,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    details: dict[str, object] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session_factory: SessionFactory | None = None,
) -> dict[str, object]:
    normalized_action = str(action).strip()
    if not normalized_action:
        raise ValueError("Audit action must not be empty.")

    event = AuditLog(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action=normalized_action,
        success=bool(success),
        details=_sanitize_details(details or {}),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    with _factory(session_factory)() as session:
        session.add(event)
        session.commit()
        session.refresh(event)
        return _record_from_model(event)
