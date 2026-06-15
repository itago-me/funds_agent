from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.jsonl_reader import read_jsonl
from src.watchlist_loader import WATCHLIST_PATH, load_watchlist_codes


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"
TASK_LOG_PATH = BASE_DIR / "logs" / "task_runs.jsonl"
SNAPSHOT_PATH = BASE_DIR / "data" / "fund_snapshots.jsonl"
WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="Funds Agent API",
    version="0.1.0",
    description="Read-only API for fund reports, task logs, snapshots, and watchlist.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


"""

@app.get("/watch_list")
def get_watch(limit: int = 20) -> dict[str, object]:
    records = read_jsonl(WATCHLIST_PATH, limit=limit)
    return {"list": records}
    }
"""


@app.get("/watchlist")
def get_watchlist() -> dict[str, object]:
    return {
        "path": str(WATCHLIST_PATH),
        "fund_codes": load_watchlist_codes(),
    }


@app.get("/reports")
def list_reports(limit: int = 20) -> dict[str, object]:
    records = read_jsonl(REPORT_INDEX_PATH, limit=limit)
    return {
        "count": len(records),
        "reports": records,
    }


@app.get("/reports/latest")
def get_latest_report() -> dict[str, object]:
    records = read_jsonl(REPORT_INDEX_PATH, limit=1)
    if not records:
        raise HTTPException(status_code=404, detail="No report index records found")

    record = records[-1]
    report_path = Path(str(record.get("report_path", "")))
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Latest report file not found")

    return {
        "metadata": record,
        "content": report_path.read_text(encoding="utf-8"),
    }


@app.get("/task-runs")
def list_task_runs(limit: int = 20) -> dict[str, object]:
    records = read_jsonl(TASK_LOG_PATH, limit=limit)
    return {
        "count": len(records),
        "task_runs": records,
    }


@app.get("/fund-snapshots")
def list_fund_snapshots(limit: int = 50) -> dict[str, object]:
    records = read_jsonl(SNAPSHOT_PATH, limit=limit)
    return {
        "count": len(records),
        "snapshots": records,
    }


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
