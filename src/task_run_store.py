"""Database-backed task run storage with JSONL compatibility."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import func, select

from src.db import get_session_factory
from src.models import Report, TaskRun
from src.report_store import load_report_records


BASE_DIR = Path(__file__).resolve().parent.parent
TASK_LOG_PATH = BASE_DIR / "logs" / "task_runs.jsonl"
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"
SessionFactory = Callable[[], AbstractContextManager]


def _default_session_factory() -> SessionFactory:
    return get_session_factory()


def _normalize_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _normalize_dict(value: object) -> dict[str, object] | None:
    return value if isinstance(value, dict) else None


def _parse_datetime(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value:
        return datetime.fromisoformat(str(value))
    return None


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
            records.append({"task_id": line_number, **record})
    return records


def _build_report_lookup(
    *,
    report_index_path: Path,
    session_factory: SessionFactory | None = None,
) -> tuple[dict[int, dict[str, object]], dict[str, dict[str, object]]]:
    by_id: dict[int, dict[str, object]] = {}
    by_path: dict[str, dict[str, object]] = {}
    for record in load_report_records(
        session_factory=session_factory,
        report_index_path=report_index_path,
    ):
        report_id = record.get("report_id")
        if isinstance(report_id, int):
            summary = _build_report_link_summary(record)
            by_id[report_id] = summary
            report_path = str(record.get("report_path") or "")
            if report_path:
                by_path[report_path] = summary
    return by_id, by_path


def _build_report_link_summary(record: dict[str, object]) -> dict[str, object]:
    report_path = Path(str(record.get("report_path") or ""))
    return {
        "report_id": record.get("report_id"),
        "report_date": record.get("report_date"),
        "report_file_name": report_path.name,
        "report_exists": report_path.exists(),
    }


def _enrich_report_link(
    record: dict[str, object],
    *,
    report_lookup_by_id: dict[int, dict[str, object]],
    report_lookup_by_path: dict[str, dict[str, object]],
) -> dict[str, object]:
    task_run = dict(record)
    report_id = task_run.get("report_id")
    report_path = str(task_run.get("report_path") or "")
    if isinstance(report_id, int) and report_id in report_lookup_by_id:
        task_run.update(report_lookup_by_id[report_id])
    elif report_path in report_lookup_by_path:
        task_run.update(report_lookup_by_path[report_path])
    elif report_path:
        task_run["report_file_name"] = Path(report_path).name
        task_run["report_exists"] = Path(report_path).exists()
    return task_run


def _record_from_model(task_run: TaskRun) -> dict[str, object]:
    record: dict[str, object] = {
        "task_id": task_run.id,
        "report_id": task_run.report_id,
        "started_at": _format_datetime(task_run.started_at),
        "finished_at": _format_datetime(task_run.finished_at),
        "status": task_run.status,
        "duration_seconds": float(task_run.duration_seconds)
        if task_run.duration_seconds is not None
        else None,
        "data_source": task_run.data_source,
        "analysis_mode": task_run.analysis_mode,
        "fund_codes": _normalize_list(task_run.fund_codes),
        "report_path": task_run.report_path,
        "warnings": _normalize_list(task_run.warnings),
        "warnings_count": task_run.warnings_count,
        "run_options": _normalize_dict(task_run.run_options),
        "error": task_run.error,
        "error_type": task_run.error_type,
    }
    return {key: value for key, value in record.items() if value is not None}


def _find_report_id_for_record(session: object, record: dict[str, object]) -> int | None:
    report_id = record.get("report_id")
    if isinstance(report_id, int):
        return report_id

    report_path = str(record.get("report_path") or "")
    if not report_path:
        return None

    result = session.execute(
        select(Report.id).where(Report.report_path == report_path)
    ).scalar_one_or_none()
    return int(result) if result is not None else None


def _model_from_record(session: object, record: dict[str, object]) -> TaskRun:
    warnings = _normalize_list(record.get("warnings"))
    started_at = _parse_datetime(record.get("started_at")) or datetime.now().replace(microsecond=0)
    duration = record.get("duration_seconds")
    return TaskRun(
        report_id=_find_report_id_for_record(session, record),
        started_at=started_at,
        finished_at=_parse_datetime(record.get("finished_at")),
        status=str(record.get("status") or "unknown"),
        duration_seconds=Decimal(str(duration)) if duration is not None else None,
        data_source=str(record.get("data_source")) if record.get("data_source") is not None else None,
        analysis_mode=str(record.get("analysis_mode")) if record.get("analysis_mode") is not None else None,
        fund_codes=_normalize_list(record.get("fund_codes")),
        report_path=str(record.get("report_path")) if record.get("report_path") is not None else None,
        warnings=warnings,
        warnings_count=int(record.get("warnings_count") or len(warnings)),
        run_options=_normalize_dict(record.get("run_options")),
        error=str(record.get("error")) if record.get("error") is not None else None,
        error_type=str(record.get("error_type")) if record.get("error_type") is not None else None,
    )


def _append_jsonl_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_record = {key: value for key, value in record.items() if key != "task_id"}
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(backup_record, ensure_ascii=False) + "\n")


def _seed_database_from_jsonl(
    session: object,
    records: list[dict[str, object]],
    *,
    report_lookup_by_id: dict[int, dict[str, object]],
    report_lookup_by_path: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    for record in records:
        session.add(_model_from_record(session, record))
    session.commit()
    task_runs = session.execute(select(TaskRun).order_by(TaskRun.id.asc())).scalars().all()
    return [
        _enrich_report_link(
            _record_from_model(task_run),
            report_lookup_by_id=report_lookup_by_id,
            report_lookup_by_path=report_lookup_by_path,
        )
        for task_run in task_runs
    ]


def load_task_run_records(
    *,
    session_factory: SessionFactory | None = None,
    task_log_path: Path = TASK_LOG_PATH,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> list[dict[str, object]]:
    report_lookup_by_id, report_lookup_by_path = _build_report_lookup(
        report_index_path=report_index_path,
        session_factory=session_factory,
    )
    jsonl_records = _load_records_from_jsonl(task_log_path)
    factory = session_factory or _default_session_factory()
    try:
        with factory() as session:
            task_runs = session.execute(
                select(TaskRun).order_by(TaskRun.id.asc())
            ).scalars().all()
            if task_runs:
                return [
                    _enrich_report_link(
                        _record_from_model(task_run),
                        report_lookup_by_id=report_lookup_by_id,
                        report_lookup_by_path=report_lookup_by_path,
                    )
                    for task_run in task_runs
                ]
            if jsonl_records:
                return _seed_database_from_jsonl(
                    session,
                    jsonl_records,
                    report_lookup_by_id=report_lookup_by_id,
                    report_lookup_by_path=report_lookup_by_path,
                )
    except Exception:
        return [
            _enrich_report_link(
                record,
                report_lookup_by_id=report_lookup_by_id,
                report_lookup_by_path=report_lookup_by_path,
            )
            for record in jsonl_records
        ]

    return []


def query_task_run_records(
    *,
    status_value: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    has_report: bool | None = None,
    failed_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    session_factory: SessionFactory | None = None,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> tuple[list[dict[str, object]], int]:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    normalized_status = status_value.strip() if status_value else None
    report_lookup_by_id, report_lookup_by_path = _build_report_lookup(
        report_index_path=report_index_path,
        session_factory=session_factory,
    )
    factory = session_factory or _default_session_factory()

    with factory() as session:
        filters = []
        if failed_only:
            filters.append(TaskRun.status == "failed")
        elif normalized_status:
            filters.append(TaskRun.status == normalized_status)
        if start_date is not None:
            filters.append(TaskRun.started_at >= datetime.combine(start_date, time.min))
        if end_date is not None:
            filters.append(TaskRun.started_at <= datetime.combine(end_date, time.max))
        if has_report is True:
            filters.append(TaskRun.report_id.is_not(None))
        elif has_report is False:
            filters.append(TaskRun.report_id.is_(None))

        total = session.execute(
            select(func.count()).select_from(TaskRun).where(*filters)
        ).scalar_one()
        task_runs = session.execute(
            select(TaskRun)
            .where(*filters)
            .order_by(TaskRun.started_at.desc(), TaskRun.id.desc())
            .limit(normalized_limit)
            .offset(normalized_offset)
        ).scalars().all()

    records = [
        _enrich_report_link(
            _record_from_model(task_run),
            report_lookup_by_id=report_lookup_by_id,
            report_lookup_by_path=report_lookup_by_path,
        )
        for task_run in task_runs
    ]
    return records, int(total)


def append_task_run_record(
    record: dict[str, object],
    *,
    session_factory: SessionFactory | None = None,
    task_log_path: Path = TASK_LOG_PATH,
    report_index_path: Path = REPORT_INDEX_PATH,
) -> None:
    factory = session_factory or _default_session_factory()
    try:
        with factory() as session:
            session.add(_model_from_record(session, record))
            session.commit()
    except Exception:
        pass

    _append_jsonl_record(task_log_path, record)
