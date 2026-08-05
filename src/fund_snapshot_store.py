"""Database-backed fund snapshot storage with JSONL compatibility."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from src.db import get_session_factory
from src.models import FundSnapshot


BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = BASE_DIR / "data" / "fund_snapshots.jsonl"
SessionFactory = Callable[[], AbstractContextManager]


def _default_session_factory() -> SessionFactory:
    return get_session_factory()


def load_fund_snapshots(
    fund_code: object,
    limit: int = 20,
    *,
    session_factory: SessionFactory | None = None,
    snapshot_path: Path = SNAPSHOT_PATH,
) -> dict[str, object]:
    normalized_code = normalize_fund_code(fund_code)
    normalized_limit = _normalize_limit(limit, maximum=200)
    snapshots = [
        record
        for record in load_snapshot_records(
            session_factory=session_factory,
            snapshot_path=snapshot_path,
        )
        if str(record.get("fund_code", "")) == normalized_code
    ]
    latest_first = list(reversed(snapshots))

    return {
        "fund_code": normalized_code,
        "count": len(latest_first[:normalized_limit]),
        "total": len(latest_first),
        "limit": normalized_limit,
        "snapshots": latest_first[:normalized_limit],
    }


def load_snapshot_records(
    *,
    limit: int | None = None,
    session_factory: SessionFactory | None = None,
    snapshot_path: Path = SNAPSHOT_PATH,
) -> list[dict[str, object]]:
    jsonl_records = _load_records_from_jsonl(snapshot_path)
    factory = session_factory or _default_session_factory()

    try:
        with factory() as session:
            snapshots = session.execute(
                select(FundSnapshot).order_by(FundSnapshot.id.asc())
            ).scalars().all()
            if snapshots:
                return _apply_limit(
                    [_record_from_model(snapshot) for snapshot in snapshots],
                    limit,
                )

            if jsonl_records:
                return _apply_limit(
                    _seed_database_from_jsonl(session, jsonl_records),
                    limit,
                )
    except Exception:
        return _apply_limit(jsonl_records, limit)

    return []


def normalize_fund_code(fund_code: object) -> str:
    normalized = str(fund_code).strip()
    if not normalized:
        raise ValueError("fund_code must not be empty")
    return normalized


def append_fund_snapshots(
    funds: list[dict[str, object]],
    report_date: str,
    data_source: str,
    *,
    session_factory: SessionFactory | None = None,
    snapshot_path: Path = SNAPSHOT_PATH,
) -> None:
    created_at = datetime.now().isoformat(timespec="seconds")
    records = [
        {
            "created_at": created_at,
            "report_date": report_date,
            "data_source": data_source,
            "fund_code": str(fund.get("fund_code", "")),
            "fund_name": str(fund.get("fund_name", "")),
            "theme": str(fund.get("theme", "")),
            "nav": _json_number(fund.get("nav")),
            "nav_date": fund.get("nav_date"),
            "daily_change_percent": _json_number(fund.get("daily_change_percent")),
            "risk_level": fund.get("risk_level"),
            "change_summary": fund.get("change_summary"),
        }
        for fund in funds
    ]

    factory = session_factory or _default_session_factory()
    try:
        with factory() as session:
            for record in records:
                session.add(_model_from_record(record))
            session.commit()
    except Exception:
        pass

    _append_jsonl_records(snapshot_path, records)


def load_latest_snapshots_by_code(
    *,
    session_factory: SessionFactory | None = None,
    snapshot_path: Path = SNAPSHOT_PATH,
) -> dict[str, dict[str, object]]:
    snapshots: dict[str, dict[str, object]] = {}

    for record in load_snapshot_records(
        session_factory=session_factory,
        snapshot_path=snapshot_path,
    ):
        fund_code = str(record.get("fund_code", ""))
        if fund_code:
            snapshots[fund_code] = record

    return snapshots


def enrich_funds_with_snapshot_comparison(
    funds: list[dict[str, object]],
    previous_snapshots: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for fund in funds:
        fund_code = str(fund.get("fund_code", ""))
        previous = previous_snapshots.get(fund_code)
        enriched.append(
            {
                **fund,
                "snapshot_comparison": build_snapshot_comparison(fund, previous),
            }
        )
    return enriched


def build_snapshot_comparison(
    current: dict[str, object],
    previous: dict[str, object] | None,
) -> dict[str, object]:
    if previous is None:
        return {
            "has_previous_snapshot": False,
            "summary": "No previous fund snapshot found.",
        }

    current_nav = to_float(current.get("nav"))
    previous_nav = to_float(previous.get("nav"))
    nav_change = None
    nav_change_percent = None
    if current_nav is not None and previous_nav not in (None, 0):
        nav_change = round(current_nav - previous_nav, 4)
        nav_change_percent = round(nav_change / previous_nav * 100, 2)

    current_risk = str(current.get("risk_level", "unknown"))
    previous_risk = str(previous.get("risk_level", "unknown"))

    parts: list[str] = []
    if nav_change is not None and nav_change_percent is not None:
        parts.append(
            f"NAV changed from {previous_nav} to {current_nav}, "
            f"{nav_change:+.4f} ({nav_change_percent:+.2f}%)."
        )
    else:
        parts.append("NAV comparison is unavailable due to missing previous data.")

    if current_risk != previous_risk:
        parts.append(f"Risk level changed from {previous_risk} to {current_risk}.")
    else:
        parts.append(f"Risk level stayed at {current_risk}.")

    return {
        "has_previous_snapshot": True,
        "previous_report_date": previous.get("report_date", "unknown"),
        "previous_nav_date": previous.get("nav_date", "unknown"),
        "previous_nav": previous.get("nav"),
        "previous_risk_level": previous_risk,
        "nav_change": nav_change,
        "nav_change_percent": nav_change_percent,
        "summary": " ".join(parts),
    }


def to_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_limit(limit: int, *, maximum: int) -> int:
    return max(1, min(limit, maximum))


def _apply_limit(
    records: list[dict[str, object]],
    limit: int | None,
) -> list[dict[str, object]]:
    if limit is None:
        return records
    return records[-_normalize_limit(limit, maximum=500):]


def _load_records_from_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []

    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _append_jsonl_records(
    path: Path,
    records: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _seed_database_from_jsonl(
    session: object,
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    for record in records:
        session.add(_model_from_record(record))
    session.commit()
    snapshots = session.execute(
        select(FundSnapshot).order_by(FundSnapshot.id.asc())
    ).scalars().all()
    return [_record_from_model(snapshot) for snapshot in snapshots]


def _model_from_record(record: dict[str, object]) -> FundSnapshot:
    return FundSnapshot(
        created_at=_parse_datetime(record.get("created_at")),
        report_date=_parse_date(record.get("report_date")),
        data_source=str(record.get("data_source") or ""),
        fund_code=str(record.get("fund_code") or ""),
        fund_name=str(record.get("fund_name") or ""),
        theme=_optional_string(record.get("theme")),
        nav=_parse_decimal(record.get("nav")),
        nav_date=_parse_optional_date(record.get("nav_date")),
        daily_change_percent=_parse_decimal(record.get("daily_change_percent")),
        risk_level=_optional_string(record.get("risk_level")),
        change_summary=_optional_string(record.get("change_summary")),
    )


def _record_from_model(snapshot: FundSnapshot) -> dict[str, object]:
    return {
        "snapshot_id": snapshot.id,
        "created_at": _format_datetime(snapshot.created_at),
        "report_date": _format_date(snapshot.report_date),
        "data_source": snapshot.data_source,
        "fund_code": snapshot.fund_code,
        "fund_name": snapshot.fund_name,
        "theme": snapshot.theme,
        "nav": _format_decimal(snapshot.nav),
        "nav_date": _format_date(snapshot.nav_date),
        "daily_change_percent": _format_decimal(snapshot.daily_change_percent),
        "risk_level": snapshot.risk_level,
        "change_summary": snapshot.change_summary,
    }


def _parse_datetime(value: object | None) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        return datetime.fromisoformat(str(value))
    return datetime.now().replace(microsecond=0)


def _parse_date(value: object | None) -> date:
    parsed = _parse_optional_date(value)
    if parsed is None:
        raise ValueError("snapshot report_date is required")
    return parsed


def _parse_optional_date(value: object | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value:
        return date.fromisoformat(str(value))
    return None


def _parse_decimal(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _format_date(value: object) -> object:
    return value.isoformat() if isinstance(value, date) else value


def _format_datetime(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


def _format_decimal(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _json_number(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _optional_string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
