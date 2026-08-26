"""该模块初步阶段使用fastapi来构建一个简单的用于前后端连接的api,现阶段只是在前端展示了后端已有的内容，后面将会接入具体的业务运行逻辑，需要一定的响应时间"""

from __future__ import annotations

from datetime import date
import os
from threading import Lock
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from main import run_daily_report
from src.fund_service import lookup_fund
from src.fund_snapshot_store import (
    load_fund_snapshot_trend,
    load_fund_snapshots,
    load_snapshot_records,
)
from src.database_status import load_database_status
from src.auth_service import (
    authenticate_user,
    load_current_user,
    public_user_payload,
    require_admin_user,
    require_authenticated_user,
)
from src.auth_session import (
    SESSION_COOKIE_NAME,
    create_session,
    delete_session,
)
from src.authorization import ROLE_ADMIN
from src.models import User
from src.redis_client import check_redis_connection
from src.report_queue import REPORT_QUEUE_KEY, enqueue_report_task
import src.report_index as report_index
from src.report_index import (
    build_report_summary,
    load_latest_report_detail,
    load_report_detail,
    load_report_records,
    load_report_summaries,
)
from src.task_logger import finish_task_failed, finish_task_success, start_task
from src.task_run_store import (
    create_pending_task_run,
    load_task_run_records as load_task_run_records_from_store,
    query_task_run_records,
    update_task_run_status,
)
from src.task_status import read_task_progress
from src.user_admin_service import (
    LastAdminProtectionError,
    SelfModificationError,
    UserNotFoundError,
    list_users,
    reset_user_password,
    update_user,
)
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


def _user_id_or_none(current_user: User | None) -> int | None:
    return current_user.id if isinstance(current_user, User) else None


def _user_kwargs(current_user: User | None) -> dict[str, int]:
    user_id = _user_id_or_none(current_user)
    return {"user_id": user_id} if user_id is not None else {}


def _load_user_watchlist(current_user: User | None) -> list[str]:
    user_id = _user_id_or_none(current_user)
    if user_id is None:
        return load_watchlist_codes()
    return load_watchlist_codes(user_id=user_id)


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


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AdminUserUpdateRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class AdminUserPasswordResetRequest(BaseModel):
    password: str = Field(min_length=8)


app = FastAPI(
    title="Funds Agent API",
    version="0.1.0",
    description="API for reading fund reports and triggering daily report generation.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/database/status")
def get_database_status(
    _current_user: User = Depends(require_admin_user),
) -> dict[str, object]:
    try:
        return load_database_status()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc


@app.get("/redis/status")
def get_redis_status(
    _current_user: User = Depends(require_admin_user),
) -> dict[str, object]:
    try:
        return check_redis_connection()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable.",
        ) from exc


def _auth_cookie_secure() -> bool:
    return os.environ.get("AUTH_COOKIE_SECURE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@app.post("/auth/login")
def login(request: LoginRequest, response: Response) -> dict[str, object]:
    user = authenticate_user(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    session_id = create_session(user_id=user.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=_auth_cookie_secure(),
        samesite="lax",
    )
    return {
        "status": "success",
        "message": "Login successful.",
        "user": public_user_payload(user),
    }


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    delete_session(request.cookies.get(SESSION_COOKIE_NAME))
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        secure=_auth_cookie_secure(),
        httponly=True,
        samesite="lax",
    )
    return {"status": "success", "message": "Logout successful."}


@app.get("/auth/me")
def get_current_user(request: Request) -> dict[str, object]:
    user = load_current_user(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return {"user": public_user_payload(user)}


@app.get("/admin/users")
def list_admin_users(
    _current_user: User = Depends(require_admin_user),
) -> dict[str, object]:
    try:
        users = list_users()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return {
        "count": len(users),
        "users": users,
    }


@app.patch("/admin/users/{user_id}")
def update_admin_user(
    user_id: int,
    request: AdminUserUpdateRequest,
    current_admin: User = Depends(require_admin_user),
) -> dict[str, object]:
    try:
        user = update_user(
            user_id=user_id,
            current_admin_id=current_admin.id,
            role=request.role,
            is_active=request.is_active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SelfModificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LastAdminProtectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return {
        "status": "success",
        "message": "User updated.",
        "user": public_user_payload(user),
    }


@app.post("/admin/users/{user_id}/password")
def reset_admin_user_password(
    user_id: int,
    request: AdminUserPasswordResetRequest,
    _current_user: User = Depends(require_admin_user),
) -> dict[str, object]:
    try:
        user = reset_user_password(user_id, request.password)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return {
        "status": "success",
        "message": "User password reset.",
        "user": public_user_payload(user),
    }


def build_report_run_options(request: ReportRunRequest) -> dict[str, object]:
    return {
        "codes": request.codes,
        "use_watchlist": request.use_watchlist,
        "use_real_data": request.use_real_data,
        "use_llm": request.use_llm,
    }


def load_task_run_records(user_id: int | None = None) -> list[dict[str, object]]:
    return load_task_run_records_from_store(
        user_id=user_id,
        task_log_path=TASK_LOG_PATH,
        report_index_path=report_index.REPORT_INDEX_PATH,
    )


def load_task_run_by_id(task_id: int, *, user_id: int | None = None) -> dict[str, object] | None:
    if task_id < 1:
        return None
    for task_run in load_task_run_records(user_id=user_id):
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


def build_schedule_status(
    today: str | None = None,
    *,
    user_id: int | None = None,
) -> dict[str, object]:
    today_value = today or date.today().isoformat()
    task_runs = load_task_run_records(user_id=user_id)
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
            codes=run_options.get("codes")
            if isinstance(run_options.get("codes"), list)
            else None,
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
def get_fund(
    fund_code: str,
    use_real_data: bool = True,
    _current_user: User = Depends(require_authenticated_user),
) -> dict[str, object]:
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
def get_fund_snapshots(
    fund_code: str,
    limit: int = 20,
    _current_user: User = Depends(require_authenticated_user),
) -> dict[str, object]:
    try:
        return load_fund_snapshots(fund_code=fund_code, limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.get("/funds/{fund_code}/trend")
def get_fund_snapshot_trend(
    fund_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    _current_user: User = Depends(require_authenticated_user),
) -> dict[str, object]:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be earlier than or equal to end_date.",
        )

    try:
        return load_fund_snapshot_trend(
            fund_code=fund_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc


@app.get("/watchlist")
def get_watchlist(
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    fund_codes = _load_user_watchlist(current_user)
    return {
        "path": str(WATCHLIST_PATH),
        "count": len(fund_codes),
        "fund_codes": fund_codes,
    }


@app.put("/watchlist")
def update_watchlist(
    request: WatchlistUpdateRequest,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    user_id = _user_id_or_none(current_user)
    if user_id is None:
        fund_codes = save_watchlist_codes(request.fund_codes)
    else:
        fund_codes = save_watchlist_codes(request.fund_codes, user_id=user_id)
    return {
        "status": "success",
        "message": "Watchlist updated.",
        "path": str(WATCHLIST_PATH),
        "count": len(fund_codes),
        "fund_codes": fund_codes,
    }


@app.post("/watchlist/funds", status_code=status.HTTP_201_CREATED)
def add_watchlist_fund(
    request: WatchlistFundRequest,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    try:
        user_id = _user_id_or_none(current_user)
        if user_id is None:
            fund_codes, added = add_watchlist_code(request.fund_code)
        else:
            fund_codes, added = add_watchlist_code(
                request.fund_code,
                user_id=user_id,
            )
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
def delete_watchlist_fund(
    fund_code: str,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    try:
        user_id = _user_id_or_none(current_user)
        if user_id is None:
            fund_codes, removed = remove_watchlist_code(fund_code)
        else:
            fund_codes, removed = remove_watchlist_code(
                fund_code,
                user_id=user_id,
            )
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
def list_reports(
    start_date: date | None = None,
    end_date: date | None = None,
    data_source: str | None = None,
    analysis_mode: str | None = None,
    fund_code: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be earlier than or equal to end_date.",
        )
    if fund_code is not None and not fund_code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fund_code must not be empty.",
        )

    try:
        return load_report_summaries(
            start_date=start_date,
            end_date=end_date,
            data_source=data_source,
            analysis_mode=analysis_mode,
            fund_code=fund_code,
            limit=limit,
            offset=offset,
            **_user_kwargs(current_user),
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc


@app.get("/reports/latest")
def get_latest_report(
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    try:
        detail = load_latest_report_detail(**_user_kwargs(current_user))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Latest report file not found: {exc}",
        ) from exc

    if detail is None:
        raise HTTPException(status_code=404, detail="No report index records found")

    return detail


@app.get("/reports/{report_id}")
def get_report_detail(
    report_id: int,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    try:
        detail = load_report_detail(
            report_id=report_id,
            **_user_kwargs(current_user),
        )
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
def run_report(
    request: ReportRunRequest,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    if request.codes is None and request.use_watchlist and not _load_user_watchlist(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Watchlist is empty. Add at least one fund code before running a watchlist report.",
        )

    if not REPORT_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A report generation task is already running.",
        )

    task = start_task(
        run_options=build_report_run_options(request),
        **_user_kwargs(current_user),
    )
    try:
        report_kwargs: dict[str, object] = {
            "codes": request.codes,
            "use_llm": request.use_llm,
            "use_real_data": request.use_real_data,
            "use_watchlist": request.use_watchlist,
        }
        user_kwargs = _user_kwargs(current_user)
        if user_kwargs:
            report_kwargs.update(user_kwargs)
        result = run_daily_report(**report_kwargs)
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


@app.post("/reports/run-async", status_code=status.HTTP_202_ACCEPTED)
def enqueue_report_run(
    request: ReportRunRequest,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    if request.codes is None and request.use_watchlist:
        fund_codes = _load_user_watchlist(current_user)
        if not fund_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Watchlist is empty. Add at least one fund code before queuing a watchlist report.",
            )
    else:
        fund_codes = [str(code) for code in (request.codes or [])]

    run_options = build_report_run_options(request)
    pending_task = create_pending_task_run(
        run_options=run_options,
        fund_codes=fund_codes,
        **_user_kwargs(current_user),
    )
    task_id = int(pending_task["task_id"])
    payload = {
        "task_id": task_id,
        "codes": fund_codes or request.codes,
        "fund_codes": fund_codes,
        "use_watchlist": request.use_watchlist,
        "use_real_data": request.use_real_data,
        "use_llm": request.use_llm,
    }
    if _user_kwargs(current_user):
        payload["user_id"] = _user_kwargs(current_user)["user_id"]

    try:
        queue_size = enqueue_report_task(payload)
    except Exception as exc:
        try:
            update_task_run_status(
                task_id=task_id,
                status_value="failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report task queue is unavailable.",
        ) from exc

    return {
        "status": "pending",
        "message": "Report task queued.",
        "task_id": task_id,
        "queue": REPORT_QUEUE_KEY,
        "queue_size": queue_size,
    }


@app.get("/task-runs")
def list_task_runs(
    status_value: Annotated[str | None, Query(alias="status")] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    has_report: bool | None = None,
    failed_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be earlier than or equal to end_date.",
        )
    if status_value is not None and not status_value.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must not be empty.",
        )

    try:
        records, total = query_task_run_records(
            status_value=status_value,
            start_date=start_date,
            end_date=end_date,
            has_report=has_report,
            failed_only=failed_only,
            limit=limit,
            offset=offset,
            **_user_kwargs(current_user),
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return {
        "count": len(records),
        "total": total,
        "limit": limit,
        "offset": offset,
        "task_runs": records,
    }


@app.get("/schedule/status")
def get_schedule_status(
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    return build_schedule_status(user_id=_user_id_or_none(current_user))


@app.get("/task-runs/{task_id}")
def get_task_run_detail(
    task_id: int,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    task_run = load_task_run_by_id(task_id=task_id, **_user_kwargs(current_user))
    if task_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task run record not found: {task_id}",
        )

    progress: dict[str, object] | None = None
    progress_available = True
    try:
        progress = read_task_progress(task_id=task_id)
    except Exception:
        progress_available = False

    return {
        "task_run": task_run,
        "progress": progress,
        "progress_available": progress_available,
    }


@app.post("/task-runs/{task_id}/rerun", status_code=status.HTTP_201_CREATED)
def rerun_task_run(
    task_id: int,
    current_user: User | None = Depends(require_authenticated_user),
) -> dict[str, object]:
    task_run = load_task_run_by_id(task_id=task_id, **_user_kwargs(current_user))
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
    response = run_report(request, current_user=current_user)
    return {
        **response,
        "rerun_of_task_id": task_id,
        "rerun_request": build_report_run_options(request),
    }


@app.get("/fund-snapshots")
def list_fund_snapshots(
    limit: int = 50,
    _current_user: User = Depends(require_authenticated_user),
) -> dict[str, object]:
    records = load_snapshot_records(limit=limit, snapshot_path=SNAPSHOT_PATH)
    return {
        "count": len(records),
        "snapshots": records,
    }


def _request_target(request: Request) -> str:
    query = request.url.query
    return request.url.path + (f"?{query}" if query else "")


def _login_redirect(request: Request) -> RedirectResponse:
    target = quote(_request_target(request), safe="")
    return RedirectResponse(
        url=f"/login?next={target}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/", include_in_schema=False, response_model=None)
@app.get("/index.html", include_in_schema=False, response_model=None)
def get_dashboard_page(request: Request) -> FileResponse | RedirectResponse:
    if load_current_user(request.cookies.get(SESSION_COOKIE_NAME)) is None:
        return _login_redirect(request)
    return FileResponse(WEB_DIR / "index.html")


@app.get("/login", include_in_schema=False, response_model=None)
def get_login_page(request: Request) -> FileResponse | RedirectResponse:
    if load_current_user(request.cookies.get(SESSION_COOKIE_NAME)) is not None:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(WEB_DIR / "login.html")


@app.get("/admin.html", include_in_schema=False, response_model=None)
@app.get("/admin", include_in_schema=False, response_model=None)
def get_admin_page(request: Request) -> FileResponse | RedirectResponse:
    user = load_current_user(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        return _login_redirect(request)
    if user.role != ROLE_ADMIN:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return FileResponse(WEB_DIR / "admin.html")


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
