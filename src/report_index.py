"""在本模块中，主要针对最新生成的基金相关数据与前一个最新数据做比较，最终生成最终的比较关系，为应用主模块进行服务"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"


def load_latest_report_record() -> dict[str, object] | None:
    if not REPORT_INDEX_PATH.exists():
        return None

    lines = [
        line.strip()
        for line in REPORT_INDEX_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return None

    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


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
