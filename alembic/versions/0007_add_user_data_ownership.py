"""add user ownership to private fund-agent data

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-25

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OWNERSHIP_TABLES = ("watchlist_items", "reports", "task_runs")


def _default_owner_id(bind: sa.Connection) -> int | None:
    """Choose an existing administrator as the default owner for old rows."""
    rows = bind.execute(
        sa.text("SELECT id, role FROM users ORDER BY id ASC")
    ).mappings().all()
    if not rows:
        return None

    for row in rows:
        if str(row.get("role", "")).lower() == "admin":
            return int(row["id"])
    return int(rows[0]["id"])


def _backfill_default_owner(bind: sa.Connection, owner_id: int | None) -> None:
    if owner_id is None:
        return

    for table_name in OWNERSHIP_TABLES:
        bind.execute(
            sa.text(f"UPDATE {table_name} SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": owner_id},
        )


def _drop_legacy_watchlist_uniqueness(bind: sa.Connection) -> None:
    """Remove the old global fund-code uniqueness before adding per-user uniqueness."""
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("watchlist_items"):
        if index["name"] == "ix_watchlist_items_fund_code":
            op.drop_index(index["name"], table_name="watchlist_items")

    for constraint in inspector.get_unique_constraints("watchlist_items"):
        columns = tuple(constraint.get("column_names") or ())
        name = constraint.get("name")
        if name and columns == ("fund_code",):
            op.drop_constraint(name, "watchlist_items", type_="unique")


def upgrade() -> None:
    for table_name in OWNERSHIP_TABLES:
        op.add_column(
            table_name,
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    # Offline SQL generation cannot inspect or update existing rows.
    if not context.is_offline_mode():
        bind = op.get_bind()
        _backfill_default_owner(bind, _default_owner_id(bind))
        _drop_legacy_watchlist_uniqueness(bind)

    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index("ix_task_runs_user_id", "task_runs", ["user_id"])

    op.create_foreign_key(
        "fk_watchlist_items_user_id_users",
        "watchlist_items",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_reports_user_id_users",
        "reports",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_task_runs_user_id_users",
        "task_runs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_watchlist_items_user_fund",
        "watchlist_items",
        ["user_id", "fund_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_watchlist_items_user_fund",
        "watchlist_items",
        type_="unique",
    )
    op.drop_constraint(
        "fk_task_runs_user_id_users",
        "task_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_reports_user_id_users",
        "reports",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_watchlist_items_user_id_users",
        "watchlist_items",
        type_="foreignkey",
    )
    op.drop_index("ix_task_runs_user_id", table_name="task_runs")
    op.drop_index("ix_reports_user_id", table_name="reports")
    op.drop_index("ix_watchlist_items_user_id", table_name="watchlist_items")
    for table_name in reversed(OWNERSHIP_TABLES):
        op.drop_column(table_name, "user_id")

    op.create_unique_constraint(
        "uq_watchlist_items_fund_code",
        "watchlist_items",
        ["fund_code"],
    )
    op.create_index(
        "ix_watchlist_items_fund_code",
        "watchlist_items",
        ["fund_code"],
        unique=True,
    )
