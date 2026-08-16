"""create normalized report fund associations

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11

"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    report_funds = op.create_table(
        "report_funds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("fund_code", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id",
            "fund_code",
            name="uq_report_funds_report_code",
        ),
    )
    op.create_index(
        "ix_report_funds_report_id",
        "report_funds",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        "ix_report_funds_fund_code",
        "report_funds",
        ["fund_code"],
        unique=False,
    )

    reports = sa.table(
        "reports",
        sa.column("id", sa.Integer()),
        sa.column("fund_codes", sa.JSON()),
    )
    result = op.get_bind().execute(
        sa.select(reports.c.id, reports.c.fund_codes)
    )
    if result is None:
        return
    rows = result.mappings()

    associations: list[dict[str, object]] = []
    for row in rows:
        fund_codes = row["fund_codes"]
        if isinstance(fund_codes, str):
            try:
                fund_codes = json.loads(fund_codes)
            except json.JSONDecodeError:
                fund_codes = []
        if not isinstance(fund_codes, list):
            continue

        seen: set[str] = set()
        for value in fund_codes:
            fund_code = str(value).strip()
            if not fund_code or fund_code in seen:
                continue
            seen.add(fund_code)
            associations.append(
                {"report_id": int(row["id"]), "fund_code": fund_code}
            )

    if associations:
        op.bulk_insert(report_funds, associations)


def downgrade() -> None:
    op.drop_index("ix_report_funds_fund_code", table_name="report_funds")
    op.drop_index("ix_report_funds_report_id", table_name="report_funds")
    op.drop_table("report_funds")
