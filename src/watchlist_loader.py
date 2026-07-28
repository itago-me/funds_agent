from __future__ import annotations

import json
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


def load_watchlist_codes() -> list[str]:
    if not WATCHLIST_PATH.exists():
        print("warning: watchlist.json not found. No watchlist codes loaded.")
        return []

    with WATCHLIST_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    codes = data.get("fund_codes", [])
    if not isinstance(codes, list):
        print("warning: watchlist.json field 'fund_codes' must be a list.")
        return []

    normalized_codes = normalize_fund_codes(codes)
    if not normalized_codes:
        print("warning: watchlist.json has no fund codes.")
    return normalized_codes


def save_watchlist_codes(fund_codes: list[object]) -> list[str]:
    normalized_codes = normalize_fund_codes(fund_codes)
    WATCHLIST_PATH.write_text(
        json.dumps({"fund_codes": normalized_codes}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized_codes


def add_watchlist_code(fund_code: object) -> tuple[list[str], bool]:
    normalized = normalize_fund_code(fund_code)
    fund_codes = load_watchlist_codes()
    if normalized in fund_codes:
        return fund_codes, False

    fund_codes.append(normalized)
    return save_watchlist_codes(fund_codes), True


def remove_watchlist_code(fund_code: object) -> tuple[list[str], bool]:
    normalized = normalize_fund_code(fund_code)
    fund_codes = load_watchlist_codes()
    updated_codes = [code for code in fund_codes if code != normalized]
    removed = len(updated_codes) != len(fund_codes)
    if removed:
        save_watchlist_codes(updated_codes)
    return updated_codes, removed
