from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = BASE_DIR / "watchlist.json"


def normalize_fund_code(fund_code: object) -> str:
    normalized = str(fund_code).strip()
    if not normalized:
        raise ValueError("fund_code must not be empty")
    return normalized


def normalize_fund_codes(fund_codes: list[object]) -> list[str]:
    normalized_codes: list[str] = []
    seen: set[str] = set()
    for fund_code in fund_codes:
        normalized = str(fund_code).strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_codes.append(normalized)
    return normalized_codes
