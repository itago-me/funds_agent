"""add data source to fund snapshots

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fund_snapshots",
        sa.Column(
            "data_source",
            sa.String(length=50),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.alter_column("fund_snapshots", "data_source", server_default=None)


def downgrade() -> None:
    op.drop_column("fund_snapshots", "data_source")
