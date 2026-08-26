"""Database-backed report metadata storage with JSONL compatibility."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func, select

from src.db import get_session_factory
from src.report_paths import normalize_report_path_for_storage
from src.models import Report, ReportFund
from src.watchlist_common import normalize_fund_code, normalize_fund_codes


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"
SessionFactory = Callable[[], AbstractContextManager]


def _default_session_factory() -> SessionFactory:
    return get_session_factory()


def _normalize_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _normalize_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _parse_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


def _parse_datetime(value: object | None) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        return datetime.fromisoformat(str(value))
    return datetime.now().replace(microsecond=0)


def _format_date(value: object) -> object:
    return value.isoformat() if isinstance(value, date) else value


def _format_datetime(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


def _load_records_from_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append({"report_id": line_number, **record})
    return records


def _record_matches_user_id(record: dict[str, object], user_id: int | None) -> bool:
    if user_id is None:
        return True
    return record.get("user_id") == user_id


def _record_from_model(report: Report) -> dict[str, object]:
    record: dict[str, object] = {
        "report_id": report.id,
        "user_id": report.user_id,
        "created_at": _format_datetime(report.created_at),
        "report_date": _format_date(report.report_date),
        "report_path": normalize_report_path_for_storage(report.report_path),
        "data_source": report.data_source,
        "analysis_mode": report.analysis_mode,
        "fund_codes": _normalize_list(report.fund_codes),
        "warnings": _normalize_list(report.warnings),
        "history_comparison": _normalize_dict(report.history_comparison),
    }
    return {key: value for key, value in record.items() if value is not None}


def _model_from_record(record: dict[str, object], *, user_id: int | None = None) -> Report:
    fund_codes = _normalize_list(record.get("fund_codes"))
    report = Report(
        user_id=user_id if user_id is not None else record.get("user_id"),
        created_at=_parse_datetime(record.get("created_at")),
        report_date=_parse_date(record.get("report_date")),
        report_path=normalize_report_path_for_storage(
            str(record.get("report_path") or "")
        ),
        data_source=str(record.get("data_source") or ""),
        analysis_mode=str(record.get("analysis_mode") or ""),
        fund_codes=fund_codes,
        warnings=_normalize_list(record.get("warnings")),
        history_comparison=_normalize_dict(record.get("history_comparison")),
    )
    report.report_funds = [
        ReportFund(fund_code=fund_code)
        for fund_code in normalize_fund_codes(fund_codes)
    ]
    return report


def _append_jsonl_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_record = {
        "created_at": record["created_at"],
        "report_date": record["report_date"],
        "report_path": record["report_path"],
        "data_source": record["data_source"],
        "analysis_mode": record["analysis_mode"],
        "fund_codes": record["fund_codes"],
        "warnings": record["warnings"],
        "history_comparison": record["history_comparison"],
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(backup_record, ensure_ascii=False) + "\n")


def _seed_database_from_jsonl(
    session: object,
    records: list[dict[str, object]],
    *,
    user_id: int | None = None,
) -> list[dict[str, object]]:
    for record in records:
        record_user_id = user_id if user_id is not None else record.get("user_id")
        session.add(_model_from_record(record, user_id=record_user_id))
    session.commit()
    reports = session.execute(select(Report).order_by(Report.id.asc())).scalars().all()
    return [_record_from_model(report) for report in reports]


def load_report_records(
    *,
    user_id: int | None = None,
    session_factory: SessionFactory | None = None,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> list[dict[str, object]]:
    factory = session_factory or _default_session_factory()
    jsonl_records = _load_records_from_jsonl(report_index_path)
    try:
        with factory() as session:
            query = select(Report).order_by(Report.id.asc())
            if user_id is not None:
                query = query.where(Report.user_id == user_id)
            reports = session.execute(query).scalars().all()
            if reports:
                return [_record_from_model(report) for report in reports]
            if user_id is not None:
                return []
            if jsonl_records:
                return _seed_database_from_jsonl(session, jsonl_records)
    except Exception:
        return [
            record for record in jsonl_records if _record_matches_user_id(record, user_id)
        ]

    return []


def query_report_records(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    data_source: str | None = None,
    analysis_mode: str | None = None,
    fund_code: str | None = None,
    user_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    session_factory: SessionFactory | None = None,
) -> tuple[list[dict[str, object]], int]:
    """Query report metadata in the database without loading every row."""
    conditions: list[Any] = []
    if start_date is not None:
        conditions.append(Report.report_date >= start_date)
    if end_date is not None:
        conditions.append(Report.report_date <= end_date)
    if data_source:
        conditions.append(Report.data_source == data_source)
    if analysis_mode:
        conditions.append(Report.analysis_mode == analysis_mode)
    if fund_code is not None:
        normalized_code = normalize_fund_code(fund_code)
        conditions.append(
            Report.report_funds.any(ReportFund.fund_code == normalized_code)
        )
    if user_id is not None:
        conditions.append(Report.user_id == user_id)

    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    factory = session_factory or _default_session_factory()

    with factory() as session:
        total = session.execute(
            select(func.count()).select_from(Report).where(*conditions)
        ).scalar_one()
        reports = session.execute(
            select(Report)
            .where(*conditions)
            .order_by(Report.report_date.desc(), Report.id.desc())
            .offset(normalized_offset)
            .limit(normalized_limit)
        ).scalars().all()

    return [_record_from_model(report) for report in reports], int(total)


def append_report_record(
    *,
    report_path: Path,
    report_date: str,
    data_source: str,
    analysis_mode: str,
    fund_codes: list[str] | None,
    warnings: list[str],
    history_comparison: dict[str, object] | None = None,
    user_id: int | None = None,
    session_factory: SessionFactory | None = None,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> None:
    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "report_date": report_date,
        "report_path": normalize_report_path_for_storage(report_path),
        "data_source": data_source,
        "analysis_mode": analysis_mode,
        "fund_codes": fund_codes or [],
        "warnings": warnings,
        "history_comparison": history_comparison or {},
    }
    if user_id is not None:
        record["user_id"] = user_id

    factory = session_factory or _default_session_factory()
    database_error: Exception | None = None
    try:
        with factory() as session:
            session.add(_model_from_record(record, user_id=user_id))
            session.commit()
    except Exception as exc:
        database_error = exc

    _append_jsonl_record(report_index_path, record)
    if database_error is not None:
        raise database_error
