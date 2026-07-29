"""在本模块中，主要针对最新生成的基金相关数据与前一个最新数据做比较，最终生成最终的比较关系，为应用主模块进行服务"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"


def load_report_records() -> list[dict[str, object]]:
    if not REPORT_INDEX_PATH.exists():
        return []

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        REPORT_INDEX_PATH.read_text(encoding="utf-8").splitlines(),
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


def load_report_summaries(limit: int = 20) -> dict[str, object]:
    normalized_limit = max(1, min(limit, 100))
    records = load_report_records()
    summaries = [build_report_summary(record) for record in reversed(records)]
    selected_summaries = summaries[:normalized_limit]

    return {
        "count": len(selected_summaries),
        "total": len(summaries),
        "limit": normalized_limit,
        "reports": selected_summaries,
    }


def load_report_detail(report_id: int) -> dict[str, object] | None:
    record = load_report_record_by_id(report_id=report_id)
    if record is None:
        return None
    return build_report_detail(record)


def load_latest_report_detail() -> dict[str, object] | None:
    record = load_latest_report_record()
    if record is None:
        return None
    return build_report_detail(record)


def load_report_record_by_id(report_id: int) -> dict[str, object] | None:
    for record in load_report_records():
        if record.get("report_id") == report_id:
            return record
    return None


def build_report_summary(record: dict[str, object]) -> dict[str, object]:
    fund_codes = normalize_list(record.get("fund_codes"))
    warnings = normalize_list(record.get("warnings"))
    report_path = Path(str(record.get("report_path", "")))

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
        "report_path": str(report_path),
        "report_file_name": report_path.name,
        "report_exists": report_path.exists(),
    }


def build_report_detail(record: dict[str, object]) -> dict[str, object]:
    metadata = build_report_summary(record)
    history_comparison = record.get("history_comparison")
    if not isinstance(history_comparison, dict):
        history_comparison = {}

    report_path = Path(str(record.get("report_path", "")))
    if not report_path.exists():
        raise FileNotFoundError(str(report_path))

    return {
        "metadata": {
            **metadata,
            "history_comparison": history_comparison,
        },
        "content": report_path.read_text(encoding="utf-8"),
    }


def normalize_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def load_latest_report_record() -> dict[str, object] | None:
    records = load_report_records()
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
        "previous_report_path": previous_record.get("report_path", "unknown"),
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
) -> None:
    REPORT_INDEX_PATH.parent.mkdir(exist_ok=True)
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

    with REPORT_INDEX_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
