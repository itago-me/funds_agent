from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize the Funds Agent database schema.",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Backfill local JSON/JSONL data after the schema migration finishes.",
    )
    return parser


def run_alembic_upgrade() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


def run_backfill() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "backfill_local_data_to_mysql.py")],
        check=True,
    )


def main(
    argv: list[str] | None = None,
    *,
    migrate_runner=run_alembic_upgrade,
    backfill_runner=run_backfill,
) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    migrate_runner()
    if args.backfill:
        backfill_runner()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
