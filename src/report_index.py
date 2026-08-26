"""Report metadata facade used by CLI and API code."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from src.report_paths import (
    normalize_report_path_for_storage,
    resolve_report_path as resolve_report_path_impl,
)
from src.report_store import (
    append_report_record,
    load_report_records as load_report_records_from_store,
    query_report_records,
)


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"


def load_report_records(user_id: int | None = None) -> list[dict[str, object]]:
    return load_report_records_from_store(
        user_id=user_id,
        report_index_path=REPORT_INDEX_PATH,
    )


def load_report_summaries(
    limit: int = 20,
    *,
    offset: int = 0,
    start_date: date | None = None,
    end_date: date | None = None,
    data_source: str | None = None,
    analysis_mode: str | None = None,
    fund_code: str | None = None,
    user_id: int | None = None,
    session_factory: Any | None = None,
) -> dict[str, object]:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    records, total = query_report_records(
        start_date=start_date,
        end_date=end_date,
        data_source=data_source,
        analysis_mode=analysis_mode,
        fund_code=fund_code,
        user_id=user_id,
        limit=normalized_limit,
        offset=normalized_offset,
        session_factory=session_factory,
    )
    summaries = [build_report_summary(record) for record in records]

    return {
        "count": len(summaries),
        "total": total,
        "limit": normalized_limit,
        "offset": normalized_offset,
        "reports": summaries,
    }


def load_report_detail(report_id: int, *, user_id: int | None = None) -> dict[str, object] | None:
    record = load_report_record_by_id(report_id=report_id, user_id=user_id)
    if record is None:
        return None
    return build_report_detail(record)


def load_latest_report_detail(*, user_id: int | None = None) -> dict[str, object] | None:
    record = load_latest_report_record(user_id=user_id)
    if record is None:
        return None
    return build_report_detail(record)


def load_report_record_by_id(report_id: int, *, user_id: int | None = None) -> dict[str, object] | None:
    for record in load_report_records(user_id=user_id):
        if record.get("report_id") == report_id:
            return record
    return None


def build_report_summary(record: dict[str, object]) -> dict[str, object]:
    fund_codes = normalize_list(record.get("fund_codes"))
    warnings = normalize_list(record.get("warnings"))
    stored_report_path = normalize_report_path_for_storage(
        str(record.get("report_path", ""))
    )
    report_path = resolve_report_path_impl(stored_report_path)

    return {
        "report_id": record.get("report_id"),
        "created_at": record.get("created_at"),
        "report_date": record.get("report_date"),
        "data_source": record.get("data_source"),
        "analysis_mode": record.get("analysis_mode"),
        "fund_codes": fund_codes,
        "fund_count": len(fund_codes),
        "warnings_count": len(warnings),
        "warnings": warnings,
        "report_path": stored_report_path,
        "report_file_name": report_path.name,
        "report_exists": report_path.exists(),
    }


def build_report_detail(record: dict[str, object]) -> dict[str, object]:
    metadata = build_report_summary(record)
    history_comparison = record.get("history_comparison")
    if not isinstance(history_comparison, dict):
        history_comparison = {}

    report_path = resolve_report_path_impl(
        normalize_report_path_for_storage(str(record.get("report_path", "")))
    )
    if not report_path.exists():
        raise FileNotFoundError(str(report_path))

    return {
        "metadata": {
            **metadata,
            "history_comparison": history_comparison,
        },
        "content": report_path.read_text(encoding="utf-8"),
    }


def resolve_report_path(report_path: str) -> Path:
    return resolve_report_path_impl(report_path)


def normalize_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def load_latest_report_record(*, user_id: int | None = None) -> dict[str, object] | None:
    records = load_report_records(user_id=user_id)
    if not records:
        return None
    return records[-1]


def build_history_comparison(
    previous_record: dict[str, object] | None,
    current_data_source: str,
    current_analysis_mode: str,
    current_fund_codes: list[str] | None,
    current_warnings: list[str],
) -> dict[str, object]:
    if previous_record is None:
        return {
            "has_previous_report": False,
            "summary": "No previous report record found. This is the first indexed run.",
        }

    previous_codes = set(str(code) for code in previous_record.get("fund_codes", []))
    current_codes = set(current_fund_codes or [])
    added_codes = sorted(current_codes - previous_codes)
    removed_codes = sorted(previous_codes - current_codes)

    changes: list[str] = []
    if previous_record.get("data_source") != current_data_source:
        changes.append(
            f"Data source changed from {previous_record.get('data_source')} to {current_data_source}."
        )
    if previous_record.get("analysis_mode") != current_analysis_mode:
        changes.append(
            f"Analysis mode changed from {previous_record.get('analysis_mode')} to {current_analysis_mode}."
        )
    if added_codes:
        changes.append(f"New fund codes added: {', '.join(added_codes)}.")
    if removed_codes:
        changes.append(f"Fund codes removed: {', '.join(removed_codes)}.")
    if current_warnings:
        changes.append(f"Current run has {len(current_warnings)} warning(s).")

    if not changes:
        changes.append(
            "No major runtime changes compared with the previous indexed report."
        )

    return {
        "has_previous_report": True,
        "previous_report_date": previous_record.get("report_date", "unknown"),
        "previous_report_path": normalize_report_path_for_storage(
            str(previous_record.get("report_path", "unknown"))
        ),
        "summary": " ".join(changes),
    }


def append_report_index(
    report_path: Path,
    report_date: str,
    data_source: str,
    analysis_mode: str,
    fund_codes: list[str] | None,
    warnings: list[str],
    history_comparison: dict[str, object] | None = None,
    user_id: int | None = None,
) -> None:
    append_report_record(
        report_path=report_path,
        report_date=report_date,
        data_source=data_source,
        analysis_mode=analysis_mode,
        fund_codes=fund_codes,
        warnings=warnings,
        history_comparison=history_comparison,
        user_id=user_id,
        report_index_path=REPORT_INDEX_PATH,
    )
