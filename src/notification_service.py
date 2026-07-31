"""Build and deliver desktop notifications for scheduled report runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


BASE_DIR = Path(__file__).resolve().parent.parent
TASK_LOG_PATH = BASE_DIR / "logs" / "task_runs.jsonl"
REPORT_INDEX_PATH = BASE_DIR / "reports" / "index.jsonl"
DASHBOARD_URL = os.getenv("FUNDS_AGENT_DASHBOARD_URL", "http://127.0.0.1:8001")


def _load_task_records() -> list[dict[str, object]]:
    path = TASK_LOG_PATH
    if not path.exists():
        return []

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append({"task_id": line_number, **record})
    return records


def _load_report_records() -> list[dict[str, object]]:
    """Match the existing report_index.py ID rule: one-based JSONL line number."""
    if not REPORT_INDEX_PATH.exists():
        return []

    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        REPORT_INDEX_PATH.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append({"report_id": line_number, **record})
    return records


def _latest_record(records: list[dict[str, object]]) -> dict[str, object] | None:
    return records[-1] if records else None


def _build_report_url(dashboard_url: str, report_id: object | None) -> str:
    base_url = dashboard_url.rstrip("/")
    if report_id is None:
        return f"{base_url}/"
    return f"{base_url}/?report_id={quote(str(report_id))}"


def _find_report_for_task(task: dict[str, object]) -> dict[str, object] | None:
    report_path = str(task.get("report_path") or "")
    if not report_path:
        return None

    for record in reversed(_load_report_records()):
        if str(record.get("report_path") or "") == report_path:
            return record
    return None


def build_latest_notification_event(
    dashboard_url: str = DASHBOARD_URL,
) -> dict[str, object]:
    """Create a normalized notification event from the latest task record."""
    task = _latest_record(_load_task_records())
    if task is None:
        return {
            "kind": "failure",
            "urgency": "critical",
            "task_id": None,
            "report_id": None,
            "report_url": _build_report_url(dashboard_url, None),
            "dashboard_url": dashboard_url,
            "title": "Funds Agent 任务失败",
            "message": "没有找到任务日志记录，无法确认日报是否生成。",
        }

    status = str(task.get("status") or "unknown")
    report = _find_report_for_task(task)
    report_id = report.get("report_id") if report else None

    if status == "success":
        report_url = _build_report_url(dashboard_url, report_id)
        if report_id is None:
            message = "日报生成成功，但没有找到对应的报告索引记录。"
        else:
            message = f"日报生成成功，报告编号为 #{report_id}。"
        return {
            "kind": "success",
            "urgency": "normal",
            "task_id": task.get("task_id"),
            "report_id": report_id,
            "report_url": report_url,
            "dashboard_url": dashboard_url,
            "title": "Funds Agent 日报生成成功",
            "message": message,
        }

    error = str(task.get("error") or "未提供错误信息")
    return {
        "kind": "failure",
        "urgency": "critical",
        "task_id": task.get("task_id"),
        "report_id": None,
        "report_url": _build_report_url(dashboard_url, None),
        "dashboard_url": dashboard_url,
        "title": "Funds Agent 任务失败",
        "message": f"日报任务执行失败：{error}",
    }


def build_notify_command(event: dict[str, object]) -> list[str]:
    """Build a notify-send command with a real clickable action."""
    return [
        "notify-send",
        "--app-name=Funds Agent",
        f"--urgency={event.get('urgency', 'normal')}",
        "--wait",
        "--action=open=打开报告",
        str(event.get("title") or "Funds Agent"),
        str(event.get("message") or ""),
    ]


def send_notification(
    event: dict[str, object],
    *,
    dry_run: bool = False,
) -> None:
    command = build_notify_command(event)
    if dry_run:
        print(json.dumps({"event": event, "command": command}, ensure_ascii=False))
        return

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error = result.stderr.strip() or f"notify-send exited with {result.returncode}"
        raise RuntimeError(error)

    if result.stdout.strip() == "open":
        report_url = str(event.get("report_url") or event.get("dashboard_url") or "")
        if report_url:
            subprocess.run(["xdg-open", report_url], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a desktop notification for the latest Funds Agent task.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Build a notification from the latest task log record.",
    )
    parser.add_argument(
        "--dashboard-url",
        default=DASHBOARD_URL,
        help="Dashboard base URL used for notification click actions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the event and command without calling desktop notification tools.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.latest:
        print("Use --latest to notify about the latest task.", file=sys.stderr)
        return 2

    try:
        event = build_latest_notification_event(
            dashboard_url=args.dashboard_url,
        )
        dry_run = args.dry_run or os.getenv("FUNDS_AGENT_NOTIFY_DRY_RUN") == "1"
        send_notification(event, dry_run=dry_run)
    except Exception as exc:
        print(f"Notification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
