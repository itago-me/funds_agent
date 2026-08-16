from __future__ import annotations

import json
from typing import Any, Callable

from src.data_loader import load_funds
from src.fund_snapshot_store import (
    enrich_funds_with_snapshot_comparison,
    load_latest_snapshots_by_code,
)
from src.redis_client import create_redis_client
from src.risk_analyzer import enrich_funds_with_risk
from src.watchlist_loader import normalize_fund_code


DEFAULT_FUND_LOOKUP_CACHE_TTL_SECONDS = 300
RedisClientFactory = Callable[[], Any]


def lookup_fund(
    fund_code: object,
    use_real_data: bool = True,
    *,
    redis_client_factory: RedisClientFactory | None = None,
    ttl_seconds: int = DEFAULT_FUND_LOOKUP_CACHE_TTL_SECONDS,
) -> dict[str, object]:
    normalized_code = normalize_fund_code(fund_code)
    cache_key = build_fund_lookup_cache_key(
        fund_code=normalized_code,
        use_real_data=use_real_data,
    )
    cached_result = load_cached_fund_lookup(
        cache_key=cache_key,
        redis_client_factory=redis_client_factory,
    )
    if cached_result is not None:
        return {
            **cached_result,
            "cache": {
                "hit": True,
                "available": True,
                "key": cache_key,
                "ttl_seconds": ttl_seconds,
            },
        }

    funds, data_source, warnings = load_funds(
        selected_codes=[normalized_code],
        prefer_real_data=use_real_data,
    )
    if not funds:
        raise LookupError(f"Fund code not found: {normalized_code}")

    funds = enrich_funds_with_risk(funds)
    previous_snapshots = load_latest_snapshots_by_code()
    funds = enrich_funds_with_snapshot_comparison(
        funds=funds,
        previous_snapshots=previous_snapshots,
    )

    result = {
        "fund": funds[0],
        "data_source": data_source,
        "warnings": warnings,
        "cache": {
            "hit": False,
            "available": True,
            "key": cache_key,
            "ttl_seconds": ttl_seconds,
        },
    }
    cache_available = save_cached_fund_lookup(
        cache_key=cache_key,
        value=result,
        ttl_seconds=ttl_seconds,
        redis_client_factory=redis_client_factory,
    )
    if not cache_available:
        result["cache"]["available"] = False

    return result


def build_fund_lookup_cache_key(
    *,
    fund_code: str,
    use_real_data: bool,
) -> str:
    source = "real" if use_real_data else "sample"
    return f"fund:lookup:{fund_code}:{source}"


def get_redis_client(
    redis_client_factory: RedisClientFactory | None = None,
) -> Any:
    factory = redis_client_factory or create_redis_client
    return factory()


def load_cached_fund_lookup(
    *,
    cache_key: str,
    redis_client_factory: RedisClientFactory | None = None,
) -> dict[str, object] | None:
    try:
        cached = get_redis_client(redis_client_factory).get(cache_key)
    except Exception:
        return None
    if not cached:
        return None

    try:
        decoded = json.loads(str(cached))
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def save_cached_fund_lookup(
    *,
    cache_key: str,
    value: dict[str, object],
    ttl_seconds: int,
    redis_client_factory: RedisClientFactory | None = None,
) -> bool:
    cache_value = {
        key: data
        for key, data in value.items()
        if key != "cache"
    }
    try:
        get_redis_client(redis_client_factory).setex(
            cache_key,
            max(1, ttl_seconds),
            json.dumps(cache_value, ensure_ascii=False),
        )
    except Exception:
        return False
    return True
