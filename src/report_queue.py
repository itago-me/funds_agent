"""Redis-backed queue for asynchronous report tasks."""

from __future__ import annotations

import json
from typing import Any, Callable

from src.redis_client import create_redis_client


REPORT_QUEUE_KEY = "funds_agent:report_tasks"
RedisClientFactory = Callable[[], Any]


def _get_redis_client(
    redis_client_factory: RedisClientFactory | None = None,
) -> Any:
    factory = redis_client_factory or create_redis_client
    return factory()


def _validate_task_payload(payload: dict[str, object]) -> dict[str, object]:
    task_id = payload.get("task_id")
    if not isinstance(task_id, int) or task_id < 1:
        raise ValueError("report task payload requires a positive integer task_id")
    return payload


def enqueue_report_task(
    payload: dict[str, object],
    *,
    redis_client_factory: RedisClientFactory | None = None,
) -> int:
    validated_payload = _validate_task_payload(payload)
    return int(
        _get_redis_client(redis_client_factory).lpush(
            REPORT_QUEUE_KEY,
            json.dumps(validated_payload, ensure_ascii=False),
        )
    )


def read_report_task(
    *,
    redis_client_factory: RedisClientFactory | None = None,
) -> dict[str, object] | None:
    value = _get_redis_client(redis_client_factory).rpop(REPORT_QUEUE_KEY)
    if not value:
        return None
    decoded = json.loads(str(value))
    if not isinstance(decoded, dict):
        raise ValueError("report queue payload must be a JSON object")
    return _validate_task_payload(decoded)
