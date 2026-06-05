from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = BASE_DIR / "data" / "fund_snapshots.jsonl"


def append_fund_snapshots(
    funds: list[dict[str, object]],
    report_date: str,
    data_source: str,
) -> None:
    SNAPSHOT_PATH.parent.mkdir(exist_ok=True)
    created_at = datetime.now().isoformat(timespec="seconds")

    with SNAPSHOT_PATH.open("a", encoding="utf-8") as file:
        for fund in funds:
            record = {
                "created_at": created_at,
                "report_date": report_date,
                "data_source": data_source,
                "fund_code": str(fund.get("fund_code", "")),
                "fund_name": str(fund.get("fund_name", "")),
                "theme": str(fund.get("theme", "")),
                "nav": fund.get("nav"),
                "nav_date": fund.get("nav_date"),
                "daily_change_percent": fund.get("daily_change_percent"),
                "risk_level": fund.get("risk_level"),
                "change_summary": fund.get("change_summary"),
            }
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_latest_snapshots_by_code() -> dict[str, dict[str, object]]:
    snapshots: dict[str, dict[str, object]] = {}
    if not SNAPSHOT_PATH.exists():
        return snapshots

    for line in SNAPSHOT_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        fund_code = str(record.get("fund_code", ""))
        if fund_code:
            snapshots[fund_code] = record

    return snapshots


def enrich_funds_with_snapshot_comparison(
    funds: list[dict[str, object]],
    previous_snapshots: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for fund in funds:
        fund_code = str(fund.get("fund_code", ""))
        previous = previous_snapshots.get(fund_code)
        enriched.append(
            {
                **fund,
                "snapshot_comparison": build_snapshot_comparison(fund, previous),
            }
        )
    return enriched


def build_snapshot_comparison(
    current: dict[str, object],
    previous: dict[str, object] | None,
) -> dict[str, object]:
    if previous is None:
        return {
            "has_previous_snapshot": False,
            "summary": "No previous fund snapshot found.",
        }

    current_nav = to_float(current.get("nav"))
    previous_nav = to_float(previous.get("nav"))
    nav_change = None
    nav_change_percent = None
    if current_nav is not None and previous_nav not in (None, 0):
        nav_change = round(current_nav - previous_nav, 4)
        nav_change_percent = round(nav_change / previous_nav * 100, 2)

    current_risk = str(current.get("risk_level", "unknown"))
    previous_risk = str(previous.get("risk_level", "unknown"))

    parts: list[str] = []
    if nav_change is not None and nav_change_percent is not None:
        parts.append(
            f"NAV changed from {previous_nav} to {current_nav}, "
            f"{nav_change:+.4f} ({nav_change_percent:+.2f}%)."
        )
    else:
        parts.append("NAV comparison is unavailable due to missing previous data.")

    if current_risk != previous_risk:
        parts.append(f"Risk level changed from {previous_risk} to {current_risk}.")
    else:
        parts.append(f"Risk level stayed at {current_risk}.")

    return {
        "has_previous_snapshot": True,
        "previous_report_date": previous.get("report_date", "unknown"),
        "previous_nav_date": previous.get("nav_date", "unknown"),
        "previous_nav": previous.get("nav"),
        "previous_risk_level": previous_risk,
        "nav_change": nav_change,
        "nav_change_percent": nav_change_percent,
        "summary": " ".join(parts),
    }


def to_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
