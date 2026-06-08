from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from time import perf_counter


BASE_DIR = Path(__file__).resolve().parent.parent
TASK_LOG_PATH = BASE_DIR / "logs" / "task_runs.jsonl"


def start_task() -> dict[str, object]:
    return {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "start_time": perf_counter(),
    }


def finish_task_success(
    task: dict[str, object],
    data_source: str,
    analysis_mode: str,
    fund_codes: list[str] | None,
    report_path: Path,
    warnings: list[str],
) -> None:
    finished_at = datetime.now().isoformat(timespec="seconds")
    duration_seconds = perf_counter() - float(task["start_time"])
    write_task_record(
        {
            "started_at": task["started_at"],
            "finished_at": finished_at,
            "status": "success",
            "duration_seconds": round(duration_seconds, 3),
            "data_source": data_source,
            "analysis_mode": analysis_mode,
            "fund_codes": fund_codes or [],
            "report_path": str(report_path),
            "warnings": warnings,
            "warnings_count": len(warnings),
        }
    )


def finish_task_failed(task: dict[str, object], error: Exception) -> None:
    finished_at = datetime.now().isoformat(timespec="seconds")
    duration_seconds = perf_counter() - float(task["start_time"])
    write_task_record(
        {
            "started_at": task["started_at"],
            "finished_at": finished_at,
            "status": "failed",
            "duration_seconds": round(duration_seconds, 3),
            "error": str(error),
            "error_type": type(error).__name__,
        }
    )


def write_task_record(record: dict[str, object]) -> None:
    TASK_LOG_PATH.parent.mkdir(exist_ok=True)
    with TASK_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
