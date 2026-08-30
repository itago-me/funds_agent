"""add user ownership to fund snapshots

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_foreign_key(inspector: sa.Inspector, table_name: str, fk_name: str) -> bool:
    return any(
        foreign_key["name"] == fk_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _default_owner_id(bind: sa.Connection) -> int | None:
    """Choose a default owner for existing historical snapshot rows."""
    rows = bind.execute(
        sa.text("SELECT id, role FROM users ORDER BY id ASC")
    ).mappings().all()
    if not rows:
        return None

    for row in rows:
        if str(row.get("role", "")).lower() == "admin":
            return int(row["id"])
    return int(rows[0]["id"])


def upgrade() -> None:
    inspector: sa.Inspector | None = None
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())

    if inspector is None or not _has_column(inspector, "fund_snapshots", "user_id"):
        op.add_column(
            "fund_snapshots",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    if not context.is_offline_mode():
        owner_id = _default_owner_id(op.get_bind())
        if owner_id is not None:
            op.get_bind().execute(
                sa.text(
                    "UPDATE fund_snapshots SET user_id = :user_id WHERE user_id IS NULL"
                ),
                    {"user_id": owner_id},
                )

    if inspector is None or not _has_index(
        inspector,
        "fund_snapshots",
        "ix_fund_snapshots_user_id",
    ):
        op.create_index("ix_fund_snapshots_user_id", "fund_snapshots", ["user_id"])
    if inspector is None or not _has_foreign_key(
        inspector,
        "fund_snapshots",
        "fk_fund_snapshots_user_id_users",
    ):
        op.create_foreign_key(
            "fk_fund_snapshots_user_id_users",
            "fund_snapshots",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_fund_snapshots_user_id_users",
        "fund_snapshots",
        type_="foreignkey",
    )
    op.drop_index("ix_fund_snapshots_user_id", table_name="fund_snapshots")
    op.drop_column("fund_snapshots", "user_id")
