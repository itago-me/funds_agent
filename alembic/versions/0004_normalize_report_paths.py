"""normalize report paths for container portability

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-19

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_report_path(report_path: object) -> str | None:
    if report_path is None:
        return None

    value = str(report_path)
    marker = "/reports/"
    if marker in value:
        return "reports/" + value.split(marker, maxsplit=1)[1]
    return value


def _normalize_table_paths(table_name: str) -> None:
    table = sa.table(
        table_name,
        sa.column("id", sa.Integer()),
        sa.column("report_path", sa.String(length=500)),
    )
    result = op.get_bind().execute(sa.select(table.c.id, table.c.report_path))
    if result is None:
        return

    for row in result.mappings():
        current_path = row["report_path"]
        normalized_path = _normalize_report_path(current_path)
        if normalized_path is None or normalized_path == current_path:
            continue
        op.get_bind().execute(
            table.update()
            .where(table.c.id == row["id"])
            .values(report_path=normalized_path)
        )


def upgrade() -> None:
    _normalize_table_paths("reports")
    _normalize_table_paths("task_runs")


def downgrade() -> None:
    pass
