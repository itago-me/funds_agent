"""One-shot local JSON/JSONL to database backfill helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from src.db import get_session_factory
from src.models import FundSnapshot, Report, TaskRun, WatchlistItem
from src.fund_snapshot_store import SNAPSHOT_PATH, load_snapshot_records
from src.report_store import REPORT_INDEX_PATH, load_report_records
from src.task_run_store import TASK_LOG_PATH, load_task_run_records
from src.watchlist_common import WATCHLIST_PATH
from src.watchlist_store import load_watchlist_codes


@dataclass(frozen=True)
class BackfillPaths:
    watchlist_path: Path = WATCHLIST_PATH
    report_index_path: Path = REPORT_INDEX_PATH
    task_log_path: Path = TASK_LOG_PATH
    snapshot_path: Path = SNAPSHOT_PATH


def backfill_local_data_to_database(
    *,
    session_factory: Any | None = None,
    paths: BackfillPaths | None = None,
) -> dict[str, object]:
    selected_paths = paths or BackfillPaths()
    factory = session_factory or get_session_factory()
    before_counts = _count_database_rows(factory)

    watchlist_codes = load_watchlist_codes(
        session_factory=factory,
        watchlist_path=selected_paths.watchlist_path,
    )
    reports = load_report_records(
        session_factory=factory,
        report_index_path=selected_paths.report_index_path,
    )
    task_runs = load_task_run_records(
        session_factory=factory,
        task_log_path=selected_paths.task_log_path,
        report_index_path=selected_paths.report_index_path,
    )
    snapshots = load_snapshot_records(
        session_factory=factory,
        snapshot_path=selected_paths.snapshot_path,
    )

    after_counts = _count_database_rows(factory)
    modules = {
        "watchlist": _build_module_summary(
            source_path=selected_paths.watchlist_path,
            local_count=_count_watchlist_file(selected_paths.watchlist_path),
            visible_count=len(watchlist_codes),
            before_count=before_counts["watchlist"],
            after_count=after_counts["watchlist"],
        ),
        "reports": _build_module_summary(
            source_path=selected_paths.report_index_path,
            local_count=_count_jsonl_records(selected_paths.report_index_path),
            visible_count=len(reports),
            before_count=before_counts["reports"],
            after_count=after_counts["reports"],
        ),
        "task_runs": _build_module_summary(
            source_path=selected_paths.task_log_path,
            local_count=_count_jsonl_records(selected_paths.task_log_path),
            visible_count=len(task_runs),
            before_count=before_counts["task_runs"],
            after_count=after_counts["task_runs"],
        ),
        "fund_snapshots": _build_module_summary(
            source_path=selected_paths.snapshot_path,
            local_count=_count_jsonl_records(selected_paths.snapshot_path),
            visible_count=len(snapshots),
            before_count=before_counts["fund_snapshots"],
            after_count=after_counts["fund_snapshots"],
        ),
    }
    inserted_total = sum(int(module["inserted_count"]) for module in modules.values())

    return {
        "status": "success",
        "inserted_total": inserted_total,
        "modules": modules,
    }


def _count_database_rows(session_factory: Any) -> dict[str, int]:
    try:
        with session_factory() as session:
            return {
                "watchlist": _count_model_rows(session, WatchlistItem),
                "reports": _count_model_rows(session, Report),
                "task_runs": _count_model_rows(session, TaskRun),
                "fund_snapshots": _count_model_rows(session, FundSnapshot),
            }
    except Exception as exc:
        raise RuntimeError(
            "Database tables are not available. Run `alembic upgrade head` "
            "and check MySQL connection settings before backfilling local data."
        ) from exc


def _count_model_rows(session: Any, model: Any) -> int:
    count = session.execute(select(func.count()).select_from(model)).scalar_one()
    return int(count)


def _build_module_summary(
    *,
    source_path: Path,
    local_count: int,
    visible_count: int,
    before_count: int,
    after_count: int,
) -> dict[str, object]:
    return {
        "source_path": str(source_path),
        "source_exists": source_path.exists(),
        "local_count": local_count,
        "before_count": before_count,
        "after_count": after_count,
        "visible_count": visible_count,
        "inserted_count": max(0, after_count - before_count),
    }


def _count_watchlist_file(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    fund_codes = data.get("fund_codes") if isinstance(data, dict) else None
    return len(fund_codes) if isinstance(fund_codes, list) else 0


def _count_jsonl_records(path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            count += 1
    return count
