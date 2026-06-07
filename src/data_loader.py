from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = BASE_DIR / "sample_data" / "funds.json"


def load_funds(
    selected_codes: list[str] | None = None,
    prefer_real_data: bool = False,
) -> tuple[list[dict[str, object]], str, list[str]]:
    warnings: list[str] = []
    if prefer_real_data and selected_codes:
        real_funds, real_warnings = load_real_funds(selected_codes=selected_codes)
        warnings.extend(real_warnings)
        if real_funds:
            return real_funds, "akshare", warnings

    sample_funds = load_sample_funds(selected_codes=selected_codes)
    if prefer_real_data:
        warnings.append("Real data unavailable. Falling back to sample_data.")
    if selected_codes and not sample_funds:
        warnings.append("No matching sample funds found for the selected codes.")
    return sample_funds, "sample_data", warnings


def load_sample_funds(selected_codes: list[str] | None = None) -> list[dict[str, object]]:
    with SAMPLE_DATA_PATH.open("r", encoding="utf-8") as file:
        funds: list[dict[str, object]] = json.load(file)

    if not selected_codes:
        return funds

    selected = set(selected_codes)
    return [fund for fund in funds if str(fund["fund_code"]) in selected]


def load_real_funds(selected_codes: list[str]) -> tuple[list[dict[str, object]], list[str]]:
    try:
        import akshare as ak
    except ImportError:
        return [], ["AkShare is not installed. Run: pip install -r requirements.txt"]

    funds: list[dict[str, object]] = []
    warnings: list[str] = []
    for code in selected_codes:
        try:
            funds.append(fetch_real_fund(ak=ak, fund_code=code))
        except Exception as exc:
            warnings.append(f"Failed to load real data for {code}: {exc}")
            continue
    return funds, warnings


def fetch_real_fund(ak: Any, fund_code: str) -> dict[str, object]:
    fund_names_df = ak.fund_name_em()
    matched = fund_names_df[fund_names_df["基金代码"].astype(str) == str(fund_code)]
    if matched.empty:
        raise ValueError(f"Fund code not found: {fund_code}")

    fund_row = matched.iloc[0]
    history_df = ak.fund_open_fund_info_em(
        symbol=str(fund_code),
        indicator="单位净值走势",
    )
    if history_df.empty:
        raise ValueError(f"No NAV history found for fund: {fund_code}")

    latest_row = history_df.iloc[-1]
    latest_nav = float(latest_row["单位净值"])
    latest_date = str(latest_row["净值日期"])
    nav_values = [float(value) for value in history_df["单位净值"].tail(30).tolist()]

    daily_change = 0.0
    if len(history_df) >= 2:
        previous_nav = float(history_df.iloc[-2]["单位净值"])
        if previous_nav != 0:
            daily_change = round((latest_nav - previous_nav) / previous_nav * 100, 2)

    metrics = build_nav_metrics(nav_values=nav_values)
    return {
        "fund_code": str(fund_code),
        "fund_name": str(fund_row["基金简称"]),
        "theme": str(fund_row["基金类型"]),
        "nav": latest_nav,
        "daily_change_percent": daily_change,
        "nav_date": latest_date,
        **metrics,
    }


def build_nav_metrics(nav_values: list[float]) -> dict[str, object]:
    return {
        "recent_navs": [round(value, 4) for value in nav_values[-7:]],
        "seven_day_return_percent": calculate_return_percent(nav_values, window=7),
        "thirty_day_return_percent": calculate_return_percent(nav_values, window=30),
        "max_daily_change_7d": calculate_max_daily_change(nav_values, window=7),
        "trend_7d": calculate_trend(nav_values, window=7),
        "drawdown_30d": calculate_max_drawdown(nav_values, window=30),
    }


def calculate_return_percent(nav_values: list[float], window: int) -> float | None:
    if len(nav_values) < 2:
        return None

    values = nav_values[-window:] if len(nav_values) >= window else nav_values
    start = values[0]
    end = values[-1]
    if start == 0:
        return None
    return round((end - start) / start * 100, 2)


def calculate_max_daily_change(nav_values: list[float], window: int) -> float | None:
    values = nav_values[-window:] if len(nav_values) >= window else nav_values
    if len(values) < 2:
        return None

    changes: list[float] = []
    for previous, current in zip(values, values[1:]):
        if previous != 0:
            changes.append(abs((current - previous) / previous * 100))
    if not changes:
        return None
    return round(max(changes), 2)


def calculate_trend(nav_values: list[float], window: int) -> str:
    values = nav_values[-window:] if len(nav_values) >= window else nav_values
    if len(values) < 2:
        return "unknown"

    up_days = 0
    down_days = 0
    for previous, current in zip(values, values[1:]):
        if current > previous:
            up_days += 1
        elif current < previous:
            down_days += 1

    if up_days >= max(1, len(values) - 2):
        return "up"
    if down_days >= max(1, len(values) - 2):
        return "down"
    return "mixed"


def calculate_max_drawdown(nav_values: list[float], window: int) -> float | None:
    values = nav_values[-window:] if len(nav_values) >= window else nav_values
    if len(values) < 2:
        return None

    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak != 0:
            drawdown = (value - peak) / peak * 100
            max_drawdown = min(max_drawdown, drawdown)
    return round(max_drawdown, 2)
