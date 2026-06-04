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

    daily_change = 0.0
    if len(history_df) >= 2:
        previous_nav = float(history_df.iloc[-2]["单位净值"])
        if previous_nav != 0:
            daily_change = round((latest_nav - previous_nav) / previous_nav * 100, 2)

    return {
        "fund_code": str(fund_code),
        "fund_name": str(fund_row["基金简称"]),
        "theme": str(fund_row["基金类型"]),
        "nav": latest_nav,
        "daily_change_percent": daily_change,
        "nav_date": latest_date,
    }
