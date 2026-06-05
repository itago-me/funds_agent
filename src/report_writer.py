from __future__ import annotations

from datetime import date
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports" / "daily_reports"


def write_report(content: str, report_date: date) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"daily_report_{report_date.isoformat()}.md"
    report_path.write_text(content, encoding="utf-8")
    return report_path
