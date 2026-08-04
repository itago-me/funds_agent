"""SQLAlchemy ORM models for the stage 6 database migration."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    report_path: Mapped[str] = mapped_column(String(500), nullable=False)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    fund_codes: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    history_comparison: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    task_runs: Mapped[list["TaskRun"]] = relationship(
        back_populates="report",
    )


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
    )
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analysis_mode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fund_codes: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    warnings: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_options: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    report: Mapped[Report | None] = relationship(
        back_populates="task_runs",
    )


class FundSnapshot(Base):
    __tablename__ = "fund_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fund_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fund_name: Mapped[str] = mapped_column(String(200), nullable=False)
    theme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nav: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    nav_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_change_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
