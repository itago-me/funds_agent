from __future__ import annotations

from pathlib import Path

from src.watchlist_common import (
    WATCHLIST_PATH,
    normalize_fund_code,
    normalize_fund_codes,
)


def load_watchlist_codes() -> list[str]:
    from src.watchlist_store import load_watchlist_codes as load_watchlist_codes_from_store

    return load_watchlist_codes_from_store()


def save_watchlist_codes(fund_codes: list[object]) -> list[str]:
    from src.watchlist_store import save_watchlist_codes as save_watchlist_codes_to_store

    return save_watchlist_codes_to_store(fund_codes)


def add_watchlist_code(fund_code: object) -> tuple[list[str], bool]:
    from src.watchlist_store import add_watchlist_code as add_watchlist_code_to_store

    return add_watchlist_code_to_store(fund_code)


def remove_watchlist_code(fund_code: object) -> tuple[list[str], bool]:
    from src.watchlist_store import remove_watchlist_code as remove_watchlist_code_from_store

    return remove_watchlist_code_from_store(fund_code)
