from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus, urlsplit, urlunsplit

from src.db import _load_project_env


DEFAULT_REDIS_HOST = "127.0.0.1"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DATABASE = 0


@dataclass(frozen=True)
class RedisConfig:
    host: str = DEFAULT_REDIS_HOST
    port: int = DEFAULT_REDIS_PORT
    database: int = DEFAULT_REDIS_DATABASE
    password: str = ""
    redis_url: str | None = None


def load_redis_config(
    environ: dict[str, str] | None = None,
) -> RedisConfig:
    _load_project_env()
    env = environ or os.environ
    redis_url = env.get("REDIS_URL")
    if redis_url:
        return RedisConfig(redis_url=redis_url)

    return RedisConfig(
        host=env.get("REDIS_HOST", DEFAULT_REDIS_HOST),
        port=int(env.get("REDIS_PORT", str(DEFAULT_REDIS_PORT))),
        database=int(env.get("REDIS_DATABASE", str(DEFAULT_REDIS_DATABASE))),
        password=env.get("REDIS_PASSWORD", ""),
    )


def build_redis_url(config: RedisConfig | None = None) -> str:
    selected_config = config or load_redis_config()
    if selected_config.redis_url:
        return selected_config.redis_url

    auth = (
        f":{quote_plus(selected_config.password)}@" if selected_config.password else ""
    )
    return (
        f"redis://{auth}{selected_config.host}:{selected_config.port}"
        f"/{selected_config.database}"
    )


def mask_redis_url(redis_url: str) -> str:
    parts = urlsplit(redis_url)
    if not parts.password:
        return redis_url

    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port is not None else ""
    username = quote_plus(parts.username or "")
    userinfo = f"{username}:***" if username else ":***"
    netloc = f"{userinfo}@{hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
