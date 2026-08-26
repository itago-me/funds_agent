"""add roles to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-22

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="user",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
