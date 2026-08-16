"""Shared task status values and Redis-backed progress helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from src.redis_client import create_redis_client


TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_FAILED = "failed"
TASK_STATUSES = {
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCESS,
    TASK_STATUS_FAILED,
}
DEFAULT_TASK_PROGRESS_TTL_SECONDS = 60 * 60 * 24
RedisClientFactory = Callable[[], Any]


def validate_task_status(status_value: str) -> str:
    normalized = str(status_value).strip()
    if normalized not in TASK_STATUSES:
        raise ValueError(f"Unsupported task status: {status_value}")
    return normalized


def build_task_progress_key(task_id: int) -> str:
    if task_id < 1:
        raise ValueError("task_id must be a positive integer")
    return f"task:{task_id}:progress"


def _get_redis_client(
    redis_client_factory: RedisClientFactory | None = None,
) -> Any:
    factory = redis_client_factory or create_redis_client
    return factory()


def write_task_progress(
    *,
    task_id: int,
    status_value: str,
    message: str = "",
    attempts: int = 0,
    redis_client_factory: RedisClientFactory | None = None,
    ttl_seconds: int = DEFAULT_TASK_PROGRESS_TTL_SECONDS,
) -> dict[str, object]:
    normalized_status = validate_task_status(status_value)
    progress = {
        "task_id": task_id,
        "status": normalized_status,
        "message": message,
        "attempts": attempts,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _get_redis_client(redis_client_factory).setex(
        build_task_progress_key(task_id),
        max(1, ttl_seconds),
        json.dumps(progress, ensure_ascii=False),
    )
    return progress


def read_task_progress(
    *,
    task_id: int,
    redis_client_factory: RedisClientFactory | None = None,
) -> dict[str, object] | None:
    value = _get_redis_client(redis_client_factory).get(build_task_progress_key(task_id))
    if not value:
        return None
    decoded = json.loads(str(value))
    return decoded if isinstance(decoded, dict) else None
