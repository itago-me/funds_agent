from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = BASE_DIR / "watchlist.json"


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

    normalized_codes = [str(code) for code in codes if str(code).strip()]
    if not normalized_codes:
        print("warning: watchlist.json has no fund codes.")
    return normalized_codes
