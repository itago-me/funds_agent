from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = BASE_DIR / "watchlist.json"


def load_watchlist_codes() -> list[str]:
    if not WATCHLIST_PATH.exists():
        return []

    with WATCHLIST_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    codes = data.get("fund_codes", [])
    return [str(code) for code in codes]
