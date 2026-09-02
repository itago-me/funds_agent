"""Redis-backed request throttling for authentication endpoints."""

from __future__ import annotations

from typing import Any, Callable

from src.redis_client import create_redis_client


RedisClientFactory = Callable[[], Any]
THROTTLE_PREFIX = "auth:throttle"


def _get_redis_client(redis_client_factory: RedisClientFactory | None) -> Any:
    return (redis_client_factory or create_redis_client)()


def build_throttle_key(action: str, subject: str) -> str:
    normalized_action = str(action).strip()
    normalized_subject = str(subject).strip()
    if not normalized_action:
        raise ValueError("action must not be empty")
    if not normalized_subject:
        raise ValueError("subject must not be empty")
    return f"{THROTTLE_PREFIX}:{normalized_action}:{normalized_subject}"


def record_throttle_attempt(
    *,
    action: str,
    subject: str,
    ttl_seconds: int,
    redis_client_factory: RedisClientFactory | None = None,
) -> int:
    client = _get_redis_client(redis_client_factory)
    key = build_throttle_key(action, subject)
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, max(1, int(ttl_seconds)))
    return count


def get_throttle_attempt_count(
    *,
    action: str,
    subject: str,
    redis_client_factory: RedisClientFactory | None = None,
) -> int:
    client = _get_redis_client(redis_client_factory)
    value = client.get(build_throttle_key(action, subject))
    if value in (None, ""):
        return 0
    return max(0, int(value))


def is_throttle_limited(
    *,
    action: str,
    subject: str,
    limit: int,
    redis_client_factory: RedisClientFactory | None = None,
) -> bool:
    return get_throttle_attempt_count(
        action=action,
        subject=subject,
        redis_client_factory=redis_client_factory,
    ) >= max(1, int(limit))


def clear_throttle_attempts(
    *,
    action: str,
    subject: str,
    redis_client_factory: RedisClientFactory | None = None,
) -> None:
    client = _get_redis_client(redis_client_factory)
    client.delete(build_throttle_key(action, subject))
