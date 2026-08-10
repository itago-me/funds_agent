"""该模块初步阶段使用fastapi来构建一个简单的用于前后端连接的api,现阶段只是在前端展示了后端已有的内容，后面将会接入具体的业务运行逻辑，需要一定的响应时间"""

from __future__ import annotations

from datetime import date
from threading import Lock
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from main import run_daily_report
from src.fund_service import lookup_fund
from src.fund_snapshot_store import load_fund_snapshots, load_snapshot_records
import src.report_index as report_index
from src.report_index import (
    build_report_summary,
    load_latest_report_detail,
    load_report_detail,
    load_report_records,
    load_report_summaries,
)
from src.task_logger import finish_task_failed, finish_task_success, start_task
from src.task_run_store import load_task_run_records as load_task_run_records_from_store
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


def build_report_run_options(request: ReportRunRequest) -> dict[str, object]:
    return {
        "codes": request.codes,
        "use_watchlist": request.use_watchlist,
        "use_real_data": request.use_real_data,
        "use_llm": request.use_llm,
    }


def load_task_run_records() -> list[dict[str, object]]:
    return load_task_run_records_from_store(
        task_log_path=TASK_LOG_PATH,
        report_index_path=report_index.REPORT_INDEX_PATH,
    )


def load_task_run_by_id(task_id: int) -> dict[str, object] | None:
    if task_id < 1:
        return None
    for task_run in load_task_run_records():
        if task_run.get("task_id") == task_id:
            return task_run
    return None


def get_task_run_date(task_run: dict[str, object]) -> str:
    for field_name in ("started_at", "finished_at"):
        value = task_run.get(field_name)
        if value:
            return str(value)[:10]
    return ""


def find_latest_task_run(
    task_runs: list[dict[str, object]],
    status_value: str,
) -> dict[str, object] | None:
    for task_run in reversed(task_runs):
        if task_run.get("status") == status_value:
            return task_run
    return None


def build_failure_alert(task_run: dict[str, object] | None) -> dict[str, object] | None:
    if task_run is None:
        return None
    return {
        "task_id": task_run.get("task_id"),
        "error_type": task_run.get("error_type"),
        "message": task_run.get("error") or "Task failed without an error message.",
        "started_at": task_run.get("started_at"),
        "finished_at": task_run.get("finished_at"),
    }


def build_schedule_status(today: str | None = None) -> dict[str, object]:
    today_value = today or date.today().isoformat()
    task_runs = load_task_run_records()
    latest_run = task_runs[-1] if task_runs else None
    latest_success = find_latest_task_run(task_runs, "success")
    latest_failure = find_latest_task_run(task_runs, "failed")
    today_runs = [
        task_run for task_run in task_runs if get_task_run_date(task_run) == today_value
    ]
    today_latest_run = today_runs[-1] if today_runs else None
    latest_failure_is_latest = (
        latest_failure is not None
        and latest_run is not None
        and latest_failure.get("task_id") == latest_run.get("task_id")
    )

    if latest_failure_is_latest:
        status_value = "failed"
        message = "Latest scheduled report run failed."
    elif not today_runs:
        status_value = "not_run_today"
        message = "No scheduled report run has been recorded today."
    elif today_latest_run and today_latest_run.get("status") == "success":
        status_value = "ok"
        message = "Today's scheduled report run succeeded."
    elif today_latest_run and today_latest_run.get("status") == "failed":
        status_value = "failed"
        message = "Today's scheduled report run failed."
    else:
        status_value = "unknown"
        message = "Scheduled report status is unknown."

    return {
        "status": status_value,
        "message": message,
        "today": today_value,
        "scheduler": "systemd_user_timer",
        "timer_name": "funds-agent-daily-report.timer",
        "service_name": "funds-agent-daily-report.service",
        "expected_schedule": "Mon..Fri 09:00",
        "has_run_today": bool(today_runs),
        "latest_run": latest_run,
        "today_latest_run": today_latest_run,
        "latest_success": latest_success,
        "latest_failure": latest_failure,
        "latest_failure_is_latest": latest_failure_is_latest,
        "failure_alert": build_failure_alert(latest_failure)
        if latest_failure_is_latest
        else None,
    }


def build_rerun_request_from_task(task_run: dict[str, object]) -> ReportRunRequest:
    run_options = task_run.get("run_options")
    if isinstance(run_options, dict):
        return ReportRunRequest(
            codes=run_options.get("codes") if isinstance(run_options.get("codes"), list) else None,
            use_watchlist=bool(run_options.get("use_watchlist", True)),
            use_real_data=bool(run_options.get("use_real_data", True)),
            use_llm=bool(run_options.get("use_llm", False)),
        )

    fund_codes = task_run.get("fund_codes")
    if isinstance(fund_codes, list) and fund_codes:
        return ReportRunRequest(
            codes=[str(code) for code in fund_codes],
            use_watchlist=False,
            use_real_data=task_run.get("data_source") != "sample_data",
            use_llm=str(task_run.get("analysis_mode")) == "deepseek_llm",
        )

    return ReportRunRequest(
        codes=None,
        use_watchlist=True,
        use_real_data=True,
        use_llm=False,
    )


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


@app.get("/funds/{fund_code}/snapshots")
def get_fund_snapshots(fund_code: str, limit: int = 20) -> dict[str, object]:
    try:
        return load_fund_snapshots(fund_code=fund_code, limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
    return load_report_summaries(limit=limit)


@app.get("/reports/latest")
def get_latest_report() -> dict[str, object]:
    try:
        detail = load_latest_report_detail()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Latest report file not found: {exc}",
        ) from exc

    if detail is None:
        raise HTTPException(status_code=404, detail="No report index records found")

    return detail


@app.get("/reports/{report_id}")
def get_report_detail(report_id: int) -> dict[str, object]:
    try:
        detail = load_report_detail(report_id=report_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file not found: {exc}",
        ) from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report index record not found: {report_id}",
        )

    return detail


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

    task = start_task(run_options=build_report_run_options(request))
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
    normalized_limit = max(1, min(limit, 100))
    all_records = load_task_run_records()
    records = list(reversed(all_records))[:normalized_limit]
    return {
        "count": len(records),
        "total": len(all_records),
        "limit": normalized_limit,
        "task_runs": records,
    }


@app.get("/schedule/status")
def get_schedule_status() -> dict[str, object]:
    return build_schedule_status()


@app.get("/task-runs/{task_id}")
def get_task_run_detail(task_id: int) -> dict[str, object]:
    task_run = load_task_run_by_id(task_id=task_id)
    if task_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task run record not found: {task_id}",
        )
    return {"task_run": task_run}


@app.post("/task-runs/{task_id}/rerun", status_code=status.HTTP_201_CREATED)
def rerun_task_run(task_id: int) -> dict[str, object]:
    task_run = load_task_run_by_id(task_id=task_id)
    if task_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task run record not found: {task_id}",
        )
    if task_run.get("status") != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed task runs can be rerun.",
        )

    request = build_rerun_request_from_task(task_run)
    response = run_report(request)
    return {
        **response,
        "rerun_of_task_id": task_id,
        "rerun_request": build_report_run_options(request),
    }


@app.get("/fund-snapshots")
def list_fund_snapshots(limit: int = 50) -> dict[str, object]:
    records = load_snapshot_records(limit=limit, snapshot_path=SNAPSHOT_PATH)
    return {
        "count": len(records),
        "snapshots": records,
    }


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
