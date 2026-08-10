from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.db import check_database_connection
from src.local_data_backfill import backfill_local_data_to_database


def main() -> int:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    connection = check_database_connection()
    print("MySQL connection: ok")
    print(f"Database URL: {connection['database_url']}")

    summary = backfill_local_data_to_database()
    print(f"Backfill status: {summary['status']}")
    print(f"Inserted total: {summary['inserted_total']}")

    modules = summary["modules"]
    if isinstance(modules, dict):
        for module_name, module_summary in modules.items():
            if not isinstance(module_summary, dict):
                continue
            print(
                f"- {module_name}: local={module_summary['local_count']}, "
                f"before={module_summary['before_count']}, "
                f"after={module_summary['after_count']}, "
                f"inserted={module_summary['inserted_count']}, "
                f"source={module_summary['source_path']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
