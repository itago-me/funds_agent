from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.db import check_database_connection


def main() -> int:
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    result = check_database_connection()
    print(f"MySQL connection: {result['status']}")
    print(f"Database URL: {result['database_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
