from __future__ import annotations

from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports" / "daily_reports"


def write_report(content: str, report_date: date, *, user_id: int | None = None) -> Path:
    report_dir = REPORTS_DIR
    if user_id is not None:
        report_dir = REPORTS_DIR / "users" / str(user_id)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"daily_report_{report_date.isoformat()}.md"
    report_path.write_text(content, encoding="utf-8")
    return report_path
