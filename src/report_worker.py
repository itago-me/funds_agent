"""Worker for processing queued report tasks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Callable

from main import run_daily_report
from src.redis_client import create_redis_client
from src.report_queue import read_report_task
from src.task_run_store import create_pending_task_run, load_task_run_records, update_task_run_status
from src.task_status import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCESS,
    read_task_progress,
    write_task_progress,
)


RedisClientFactory = Callable[[], Any]
ReportRunner = Callable[..., dict[str, object]]


def process_next_report_task(
    *,
    redis_client_factory: RedisClientFactory | None = None,
    report_runner: ReportRunner | None = None,
    sleep_seconds: float = 0.0,
    session_factory: Any | None = None,
    task_log_path: Path | None = None,
    report_index_path: Path | None = None,
) -> dict[str, object] | None:
    queue_client_factory = redis_client_factory or create_redis_client
    payload = read_report_task(redis_client_factory=queue_client_factory)
    if payload is None:
        return None

    task_id = int(payload["task_id"])
    runner = report_runner or run_daily_report
    _ensure_pending_task(
        payload=payload,
        session_factory=session_factory,
        task_log_path=task_log_path,
        report_index_path=report_index_path,
    )
    _mark_task_running(
        task_id=task_id,
        queue_client_factory=queue_client_factory,
        session_factory=session_factory,
        report_index_path=report_index_path,
    )

    if sleep_seconds > 0:
        sleep(sleep_seconds)

    try:
        runner_kwargs: dict[str, object] = {
            "codes": payload.get("codes"),
            "use_llm": bool(payload.get("use_llm", False)),
            "use_real_data": bool(payload.get("use_real_data", True)),
            "use_watchlist": bool(payload.get("use_watchlist", False)),
        }
        if payload.get("user_id") is not None:
            runner_kwargs["user_id"] = int(payload["user_id"])
        result = runner(
            **runner_kwargs,
        )
    except Exception as exc:
        failure = _mark_task_failed(
            task_id=task_id,
            error=exc,
            queue_client_factory=queue_client_factory,
            session_factory=session_factory,
            report_index_path=report_index_path,
        )
        return failure

    success = _mark_task_success(
        task_id=task_id,
        result=result,
        queue_client_factory=queue_client_factory,
        session_factory=session_factory,
        task_log_path=task_log_path,
        report_index_path=report_index_path,
    )
    return success


def run_report_worker(
    *,
    redis_client_factory: RedisClientFactory | None = None,
    report_runner: ReportRunner | None = None,
    poll_interval_seconds: float = 1.0,
    session_factory: Any | None = None,
    task_log_path: Path | None = None,
    report_index_path: Path | None = None,
) -> None:
    while True:
        processed = process_next_report_task(
            redis_client_factory=redis_client_factory,
            report_runner=report_runner,
            session_factory=session_factory,
            task_log_path=task_log_path,
            report_index_path=report_index_path,
        )
        if processed is None and poll_interval_seconds > 0:
            sleep(poll_interval_seconds)


def _mark_task_running(
    *,
    task_id: int,
    queue_client_factory: RedisClientFactory,
    session_factory: Any | None,
    report_index_path: Path | None,
) -> dict[str, object]:
    progress = write_task_progress(
        task_id=task_id,
        status_value=TASK_STATUS_RUNNING,
        message="running report generation",
        attempts=1,
        redis_client_factory=queue_client_factory,
    )
    return update_task_run_status(
        task_id=task_id,
        status_value=TASK_STATUS_RUNNING,
        finished_at=None,
        session_factory=session_factory,
        report_index_path=report_index_path if report_index_path is not None else Path("reports/index.jsonl"),
    )


def _mark_task_success(
    *,
    task_id: int,
    result: dict[str, object],
    queue_client_factory: RedisClientFactory,
    session_factory: Any | None,
    task_log_path: Path | None,
    report_index_path: Path | None,
) -> dict[str, object]:
    write_task_progress(
        task_id=task_id,
        status_value=TASK_STATUS_SUCCESS,
        message="report generated successfully",
        attempts=1,
        redis_client_factory=queue_client_factory,
    )
    return update_task_run_status(
        task_id=task_id,
        status_value=TASK_STATUS_SUCCESS,
        finished_at=datetime.now(),
        data_source=str(result.get("data_source") or ""),
        analysis_mode=str(result.get("analysis_mode") or ""),
        fund_codes=result.get("fund_codes") if isinstance(result.get("fund_codes"), list) else None,
        report_path=str(result.get("report_path") or ""),
        warnings=result.get("warnings") if isinstance(result.get("warnings"), list) else [],
        session_factory=session_factory,
        report_index_path=report_index_path if report_index_path is not None else Path("reports/index.jsonl"),
    )


def _mark_task_failed(
    *,
    task_id: int,
    error: Exception,
    queue_client_factory: RedisClientFactory,
    session_factory: Any | None,
    report_index_path: Path | None,
) -> dict[str, object]:
    write_task_progress(
        task_id=task_id,
        status_value=TASK_STATUS_FAILED,
        message=str(error),
        attempts=1,
        redis_client_factory=queue_client_factory,
    )
    return update_task_run_status(
        task_id=task_id,
        status_value=TASK_STATUS_FAILED,
        finished_at=datetime.now(),
        error=str(error),
        error_type=type(error).__name__,
        session_factory=session_factory,
        report_index_path=report_index_path if report_index_path is not None else Path("reports/index.jsonl"),
    )


def _ensure_pending_task(
    *,
    payload: dict[str, object],
    session_factory: Any | None,
    task_log_path: Path | None,
    report_index_path: Path | None,
) -> None:
    task_id = int(payload["task_id"])
    existing = [
        task_run
        for task_run in load_task_run_records(
            session_factory=session_factory,
            task_log_path=task_log_path if task_log_path is not None else Path("logs/task_runs.jsonl"),
            report_index_path=report_index_path if report_index_path is not None else Path("reports/index.jsonl"),
        )
        if int(task_run.get("task_id", 0)) == task_id
    ]
    if existing:
        return

    create_pending_task_run(
        task_id=task_id,
        run_options={
            "codes": payload.get("codes"),
            "use_watchlist": payload.get("use_watchlist"),
            "use_real_data": payload.get("use_real_data"),
            "use_llm": payload.get("use_llm"),
        },
        fund_codes=payload.get("fund_codes") if isinstance(payload.get("fund_codes"), list) else None,
        session_factory=session_factory,
        task_log_path=task_log_path if task_log_path is not None else Path("logs/task_runs.jsonl"),
        report_index_path=report_index_path if report_index_path is not None else Path("reports/index.jsonl"),
    )
