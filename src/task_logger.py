"""该模块实际用于主函数中进行个部分内容错误的总结，该模块中函数包含了基金分析的主要执行，使用者可以直接通过该模块定义的输出内容直观的看到基金分析的相关情况，是程序运行的直接对外表达"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter

from src.task_run_store import append_task_run_record


BASE_DIR = Path(__file__).resolve().parent.parent
TASK_LOG_PATH = BASE_DIR / "logs" / "task_runs.jsonl"


def start_task(run_options: dict[str, object] | None = None) -> dict[str, object]:
    task = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "start_time": perf_counter(),
    }
    if run_options is not None:
        task["run_options"] = run_options
    return task


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
    record = {
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
    if "run_options" in task:
        record["run_options"] = task["run_options"]
    write_task_record(record)


def finish_task_failed(task: dict[str, object], error: Exception) -> None:
    finished_at = datetime.now().isoformat(timespec="seconds")
    duration_seconds = perf_counter() - float(task["start_time"])
    record = {
        "started_at": task["started_at"],
        "finished_at": finished_at,
        "status": "failed",
        "duration_seconds": round(duration_seconds, 3),
        "error": str(error),
        "error_type": type(error).__name__,
    }
    run_options = task.get("run_options")
    if isinstance(run_options, dict):
        record["run_options"] = run_options
        codes = run_options.get("codes")
        if isinstance(codes, list):
            record["fund_codes"] = codes
    write_task_record(record)


def write_task_record(record: dict[str, object]) -> None:
    append_task_run_record(record, task_log_path=TASK_LOG_PATH)
