"""SQLAlchemy ORM models for the Funds Agent database."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base
from src.authorization import ROLE_USER


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "fund_code", name="uq_watchlist_items_user_fund"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    fund_code: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User | None"] = relationship(back_populates="watchlist_items")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ROLE_USER,
        server_default=ROLE_USER,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    watchlist_items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="user")
    task_runs: Mapped[list["TaskRun"]] = relationship(back_populates="user")
    fund_snapshots: Mapped[list["FundSnapshot"]] = relationship(back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    report_funds: Mapped[list["ReportFund"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
    )
    user: Mapped["User | None"] = relationship(back_populates="reports")


class ReportFund(Base):
    __tablename__ = "report_funds"
    __table_args__ = (
        UniqueConstraint("report_id", "fund_code", name="uq_report_funds_report_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fund_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    report: Mapped[Report] = relationship(back_populates="report_funds")


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    user: Mapped["User | None"] = relationship(back_populates="task_runs")


class FundSnapshot(Base):
    __tablename__ = "fund_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)
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

    user: Mapped["User | None"] = relationship(back_populates="fund_snapshots")
