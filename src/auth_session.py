"""Redis-backed server-side authentication sessions."""

from __future__ import annotations

import json
import os
import secrets
from typing import Any, Callable

from src.redis_client import create_redis_client


SESSION_COOKIE_NAME = "funds_agent_session"
DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
RedisClientFactory = Callable[[], Any]


def _session_ttl_seconds() -> int:
    try:
        return max(
            1,
            int(
                os.environ.get(
                    "AUTH_SESSION_TTL_SECONDS",
                    str(DEFAULT_SESSION_TTL_SECONDS),
                )
            ),
        )
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS


def get_session_ttl_seconds() -> int:
    return _session_ttl_seconds()


def build_session_key(session_id: str) -> str:
    if not session_id:
        raise ValueError("session_id must not be empty")
    return f"auth:session:{session_id}"


def _get_redis_client(redis_client_factory: RedisClientFactory | None) -> Any:
    return (redis_client_factory or create_redis_client)()


def create_session(
    *,
    user_id: int,
    redis_client_factory: RedisClientFactory | None = None,
    ttl_seconds: int | None = None,
) -> str:
    if user_id < 1:
        raise ValueError("user_id must be a positive integer")

    session_id = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": user_id}, separators=(",", ":"))
    _get_redis_client(redis_client_factory).setex(
        build_session_key(session_id),
        max(1, ttl_seconds or _session_ttl_seconds()),
        payload,
    )
    return session_id


def read_session_user_id(
    session_id: str | None,
    *,
    redis_client_factory: RedisClientFactory | None = None,
) -> int | None:
    if not session_id:
        return None

    value = _get_redis_client(redis_client_factory).get(build_session_key(session_id))
    if not value:
        return None
    try:
        payload = json.loads(str(value))
        user_id = int(payload["user_id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
    return user_id if user_id > 0 else None


def delete_session(
    session_id: str | None,
    *,
    redis_client_factory: RedisClientFactory | None = None,
) -> None:
    if session_id:
        _get_redis_client(redis_client_factory).delete(build_session_key(session_id))
