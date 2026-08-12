"""Read-only database health and core table statistics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from sqlalchemy import func, select

from src.db import get_session_factory
from src.models import FundSnapshot, Report, TaskRun, WatchlistItem


SessionFactory = Callable[[], Any]


def load_database_status(
    *,
    session_factory: SessionFactory | None = None,
) -> dict[str, object]:
    """Return database dialect, table row counts, and latest activity times."""
    factory = session_factory or get_session_factory()

    with factory() as session:
        tables = {
            "watchlist_items": _count_rows(session, WatchlistItem),
            "reports": _count_rows(session, Report),
            "task_runs": _count_rows(session, TaskRun),
            "fund_snapshots": _count_rows(session, FundSnapshot),
        }
        latest = {
            "report_created_at": _to_iso(
                session.execute(
                    select(Report.created_at).order_by(Report.created_at.desc()).limit(1)
                ).scalar_one_or_none()
            ),
            "task_started_at": _to_iso(
                session.execute(
                    select(TaskRun.started_at).order_by(TaskRun.started_at.desc()).limit(1)
                ).scalar_one_or_none()
            ),
            "snapshot_report_date": _to_iso(
                session.execute(
                    select(FundSnapshot.report_date)
                    .order_by(FundSnapshot.report_date.desc())
                    .limit(1)
                ).scalar_one_or_none()
            ),
        }

        dialect = "unknown"
        bind = getattr(session, "bind", None)
        if bind is not None:
            dialect = str(getattr(bind.dialect, "name", dialect))

    return {
        "status": "ok",
        "database": dialect,
        "message": "Database is available.",
        "tables": tables,
        "latest": latest,
    }


def _count_rows(session: Any, model: Any) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def _to_iso(value: object | None) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value) if value is not None else None
