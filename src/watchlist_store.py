"""Database-backed watchlist storage with JSON file compatibility fallback."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable, Iterable

from sqlalchemy import delete, select

from src.db import get_session_factory
from src.models import WatchlistItem
from src.watchlist_common import (
    WATCHLIST_PATH,
    normalize_fund_code,
    normalize_fund_codes,
)


SessionFactory = Callable[[], AbstractContextManager]


def _default_session_factory() -> SessionFactory:
    return get_session_factory()


def _load_codes_from_file(path: Path) -> list[str]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    codes = data.get("fund_codes", [])
    if not isinstance(codes, list):
        return []
    return normalize_fund_codes(codes)


def _write_codes_to_file(path: Path, fund_codes: Iterable[str]) -> list[str]:
    normalized_codes = normalize_fund_codes(list(fund_codes))
    path.write_text(
        json.dumps({"fund_codes": normalized_codes}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized_codes


def load_watchlist_codes(
    *,
    session_factory: SessionFactory | None = None,
    watchlist_path: Path = WATCHLIST_PATH,
) -> list[str]:
    factory = session_factory or _default_session_factory()
    with factory() as session:
        try:
            result = session.execute(
                select(WatchlistItem.fund_code).order_by(WatchlistItem.id.asc())
            ).scalars().all()
        except Exception:
            result = []

        if result:
            return normalize_fund_codes(list(result))

        file_codes = _load_codes_from_file(watchlist_path)
        if file_codes:
            for fund_code in file_codes:
                session.add(WatchlistItem(fund_code=fund_code))
            session.commit()
            return file_codes

    return []


def save_watchlist_codes(
    fund_codes: list[object],
    *,
    session_factory: SessionFactory | None = None,
    watchlist_path: Path = WATCHLIST_PATH,
) -> list[str]:
    normalized_codes = normalize_fund_codes(fund_codes)
    factory = session_factory or _default_session_factory()
    with factory() as session:
        session.execute(delete(WatchlistItem))
        for fund_code in normalized_codes:
            session.add(WatchlistItem(fund_code=fund_code))
        session.commit()

    _write_codes_to_file(watchlist_path, normalized_codes)
    return normalized_codes


def add_watchlist_code(
    fund_code: object,
    *,
    session_factory: SessionFactory | None = None,
    watchlist_path: Path = WATCHLIST_PATH,
) -> tuple[list[str], bool]:
    normalized = normalize_fund_code(fund_code)
    fund_codes = load_watchlist_codes(
        session_factory=session_factory,
        watchlist_path=watchlist_path,
    )
    if normalized in fund_codes:
        return fund_codes, False

    fund_codes.append(normalized)
    return save_watchlist_codes(
        fund_codes,
        session_factory=session_factory,
        watchlist_path=watchlist_path,
    ), True


def remove_watchlist_code(
    fund_code: object,
    *,
    session_factory: SessionFactory | None = None,
    watchlist_path: Path = WATCHLIST_PATH,
) -> tuple[list[str], bool]:
    normalized = normalize_fund_code(fund_code)
    fund_codes = load_watchlist_codes(
        session_factory=session_factory,
        watchlist_path=watchlist_path,
    )
    updated_codes = [code for code in fund_codes if code != normalized]
    removed = len(updated_codes) != len(fund_codes)
    if removed:
        save_watchlist_codes(
            updated_codes,
            session_factory=session_factory,
            watchlist_path=watchlist_path,
        )
    return updated_codes, removed
