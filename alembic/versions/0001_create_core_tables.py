"""create core funds agent tables

Revision ID: 0001
Revises:
Create Date: 2026-08-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_code"),
    )
    op.create_index(
        "ix_watchlist_items_fund_code",
        "watchlist_items",
        ["fund_code"],
        unique=True,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_path", sa.String(length=500), nullable=False),
        sa.Column("data_source", sa.String(length=50), nullable=False),
        sa.Column("analysis_mode", sa.String(length=50), nullable=False),
        sa.Column("fund_codes", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("history_comparison", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_created_at", "reports", ["created_at"], unique=False)
    op.create_index("ix_reports_report_date", "reports", ["report_date"], unique=False)

    op.create_table(
        "task_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("data_source", sa.String(length=50), nullable=True),
        sa.Column("analysis_mode", sa.String(length=50), nullable=True),
        sa.Column("fund_codes", sa.JSON(), nullable=True),
        sa.Column("report_path", sa.String(length=500), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("warnings_count", sa.Integer(), nullable=False),
        sa.Column("run_options", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_runs_report_id", "task_runs", ["report_id"], unique=False)
    op.create_index(
        "ix_task_runs_started_at", "task_runs", ["started_at"], unique=False
    )
    op.create_index("ix_task_runs_status", "task_runs", ["status"], unique=False)

    op.create_table(
        "fund_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("fund_code", sa.String(length=20), nullable=False),
        sa.Column("fund_name", sa.String(length=200), nullable=False),
        sa.Column("theme", sa.String(length=100), nullable=True),
        sa.Column("nav", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("nav_date", sa.Date(), nullable=True),
        sa.Column(
            "daily_change_percent",
            sa.Numeric(precision=10, scale=4),
            nullable=True,
        ),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fund_snapshots_report_date",
        "fund_snapshots",
        ["report_date"],
        unique=False,
    )
    op.create_index(
        "ix_fund_snapshots_fund_code",
        "fund_snapshots",
        ["fund_code"],
        unique=False,
    )
    op.create_index(
        "ix_fund_snapshots_risk_level",
        "fund_snapshots",
        ["risk_level"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fund_snapshots_risk_level", table_name="fund_snapshots")
    op.drop_index("ix_fund_snapshots_fund_code", table_name="fund_snapshots")
    op.drop_index("ix_fund_snapshots_report_date", table_name="fund_snapshots")
    op.drop_table("fund_snapshots")

    op.drop_index("ix_task_runs_status", table_name="task_runs")
    op.drop_index("ix_task_runs_started_at", table_name="task_runs")
    op.drop_index("ix_task_runs_report_id", table_name="task_runs")
    op.drop_table("task_runs")

    op.drop_index("ix_reports_report_date", table_name="reports")
    op.drop_index("ix_reports_created_at", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_watchlist_items_fund_code", table_name="watchlist_items")
    op.drop_table("watchlist_items")
