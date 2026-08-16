"""Redis connection and health check helpers."""

from __future__ import annotations

from typing import Any, Callable

from src.redis_config import build_redis_url, mask_redis_url


def _import_redis() -> Any:
    try:
        import redis
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Redis Python client is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return redis


def create_redis_client(redis_url: str | None = None) -> Any:
    redis = _import_redis()
    return redis.Redis.from_url(redis_url or build_redis_url(), decode_responses=True)


def check_redis_connection(
    redis_url: str | None = None,
    client_factory: Callable[[str], Any] | None = None,
) -> dict[str, object]:
    selected_url = redis_url or build_redis_url()
    client = client_factory(selected_url) if client_factory else create_redis_client(selected_url)

    ping_result = client.ping()
    info = client.info("server") if hasattr(client, "info") else {}

    return {
        "status": "ok" if ping_result else "error",
        "redis_url": mask_redis_url(selected_url),
        "redis_version": info.get("redis_version") if isinstance(info, dict) else None,
        "connected_clients": info.get("connected_clients") if isinstance(info, dict) else None,
    }
