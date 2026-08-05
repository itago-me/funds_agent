"""Database-backed report metadata storage with JSONL compatibility."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from src.db import get_session_factory
from src.models import Report


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


def _record_from_model(report: Report) -> dict[str, object]:
    return {
        "report_id": report.id,
        "created_at": _format_datetime(report.created_at),
        "report_date": _format_date(report.report_date),
        "report_path": report.report_path,
        "data_source": report.data_source,
        "analysis_mode": report.analysis_mode,
        "fund_codes": _normalize_list(report.fund_codes),
        "warnings": _normalize_list(report.warnings),
        "history_comparison": _normalize_dict(report.history_comparison),
    }


def _model_from_record(record: dict[str, object]) -> Report:
    return Report(
        created_at=_parse_datetime(record.get("created_at")),
        report_date=_parse_date(record.get("report_date")),
        report_path=str(record.get("report_path") or ""),
        data_source=str(record.get("data_source") or ""),
        analysis_mode=str(record.get("analysis_mode") or ""),
        fund_codes=_normalize_list(record.get("fund_codes")),
        warnings=_normalize_list(record.get("warnings")),
        history_comparison=_normalize_dict(record.get("history_comparison")),
    )


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
) -> list[dict[str, object]]:
    for record in records:
        session.add(_model_from_record(record))
    session.commit()
    reports = session.execute(select(Report).order_by(Report.id.asc())).scalars().all()
    return [_record_from_model(report) for report in reports]


def load_report_records(
    *,
    session_factory: SessionFactory | None = None,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> list[dict[str, object]]:
    factory = session_factory or _default_session_factory()
    jsonl_records = _load_records_from_jsonl(report_index_path)
    try:
        with factory() as session:
            reports = session.execute(
                select(Report).order_by(Report.id.asc())
            ).scalars().all()
            if reports:
                return [_record_from_model(report) for report in reports]
            if jsonl_records:
                return _seed_database_from_jsonl(session, jsonl_records)
    except Exception:
        return jsonl_records

    return []


def append_report_record(
    *,
    report_path: Path,
    report_date: str,
    data_source: str,
    analysis_mode: str,
    fund_codes: list[str] | None,
    warnings: list[str],
    history_comparison: dict[str, object] | None = None,
    session_factory: SessionFactory | None = None,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> None:
    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "report_date": report_date,
        "report_path": str(report_path),
        "data_source": data_source,
        "analysis_mode": analysis_mode,
        "fund_codes": fund_codes or [],
        "warnings": warnings,
        "history_comparison": history_comparison or {},
    }

    factory = session_factory or _default_session_factory()
    try:
        with factory() as session:
            session.add(_model_from_record(record))
            session.commit()
    except Exception:
        pass

    _append_jsonl_record(report_index_path, record)
