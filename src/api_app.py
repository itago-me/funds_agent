"""该模块初步阶段使用fastapi来构建一个简单的用于前后端连接的api,现阶段只是在前端展示了后端已有的内容，后面将会接入具体的业务运行逻辑，需要一定的响应时间"""

from __future__ import annotations

from threading import Lock
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import run_daily_report
from src.fund_service import lookup_fund
from src.jsonl_reader import read_jsonl
from src.task_logger import finish_task_failed, finish_task_success, start_task
from src.watchlist_loader import (
    WATCHLIST_PATH,
    add_watchlist_code,
    load_watchlist_codes,
    remove_watchlist_code,
    save_watchlist_codes,
)


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"
TASK_LOG_PATH = BASE_DIR / "logs" / "task_runs.jsonl"
SNAPSHOT_PATH = BASE_DIR / "data" / "fund_snapshots.jsonl"
WEB_DIR = BASE_DIR / "web"
REPORT_RUN_LOCK = Lock()


class ReportRunRequest(BaseModel):
    codes: list[str] | None = Field(
        default=None,
        description="Optional fund codes. When omitted and use_watchlist is true, watchlist.json is used.",
    )
    use_watchlist: bool = Field(
        default=True, description="Load fund codes from watchlist.json."
    )
    use_real_data: bool = Field(
        default=True, description="Try to load real fund data from AkShare."
    )
    use_llm: bool = Field(
        default=False, description="Use DeepSeek when DEEPSEEK_API_KEY is configured."
    )


class WatchlistUpdateRequest(BaseModel):
    fund_codes: list[str] = Field(
        default_factory=list,
        description="Fund codes to store in watchlist.json.",
    )


class WatchlistFundRequest(BaseModel):
    fund_code: str = Field(description="Fund code to add to watchlist.json.")


app = FastAPI(
    title="Funds Agent API",
    version="0.1.0",
    description="API for reading fund reports and triggering daily report generation.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/funds/{fund_code}")
def get_fund(fund_code: str, use_real_data: bool = True) -> dict[str, object]:
    try:
        return lookup_fund(fund_code=fund_code, use_real_data=use_real_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get("/watchlist")
def get_watchlist() -> dict[str, object]:
    fund_codes = load_watchlist_codes()
    return {
        "path": str(WATCHLIST_PATH),
        "count": len(fund_codes),
        "fund_codes": fund_codes,
    }


@app.put("/watchlist")
def update_watchlist(request: WatchlistUpdateRequest) -> dict[str, object]:
    fund_codes = save_watchlist_codes(request.fund_codes)
    return {
        "status": "success",
        "message": "Watchlist updated.",
        "path": str(WATCHLIST_PATH),
        "count": len(fund_codes),
        "fund_codes": fund_codes,
    }


@app.post("/watchlist/funds", status_code=status.HTTP_201_CREATED)
def add_watchlist_fund(request: WatchlistFundRequest) -> dict[str, object]:
    try:
        fund_codes, added = add_watchlist_code(request.fund_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "status": "success",
        "message": (
            "Fund added to watchlist." if added else "Fund already exists in watchlist."
        ),
        "added": added,
        "path": str(WATCHLIST_PATH),
        "count": len(fund_codes),
        "fund_codes": fund_codes,
    }


@app.delete("/watchlist/funds/{fund_code}")
def delete_watchlist_fund(fund_code: str) -> dict[str, object]:
    try:
        fund_codes, removed = remove_watchlist_code(fund_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fund code not found in watchlist: {fund_code}",
        )

    return {
        "status": "success",
        "message": "Fund removed from watchlist.",
        "removed": removed,
        "path": str(WATCHLIST_PATH),
        "count": len(fund_codes),
        "fund_codes": fund_codes,
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


@app.post("/reports/run", status_code=status.HTTP_201_CREATED)
def run_report(request: ReportRunRequest) -> dict[str, object]:
    if request.codes is None and request.use_watchlist and not load_watchlist_codes():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Watchlist is empty. Add at least one fund code before running a watchlist report.",
        )

    if not REPORT_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A report generation task is already running.",
        )

    task = start_task()
    try:
        result = run_daily_report(
            codes=request.codes,
            use_llm=request.use_llm,
            use_real_data=request.use_real_data,
            use_watchlist=request.use_watchlist,
        )
    except Exception as exc:
        finish_task_failed(task=task, error=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {exc}",
        ) from exc
    finally:
        REPORT_RUN_LOCK.release()

    warnings = result["warnings"] if isinstance(result["warnings"], list) else []
    fund_codes = result["fund_codes"] if isinstance(result["fund_codes"], list) else []
    finish_task_success(
        task=task,
        data_source=str(result["data_source"]),
        analysis_mode=str(result["analysis_mode"]),
        fund_codes=fund_codes,
        report_path=Path(str(result["report_path"])),
        warnings=warnings,
    )

    return {
        "status": "success",
        "message": "Report generated successfully.",
        "result": result,
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
