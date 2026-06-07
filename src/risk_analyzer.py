from __future__ import annotations


def enrich_funds_with_risk(funds: list[dict[str, object]]) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for fund in funds:
        change = float(str(fund.get("daily_change_percent", 0)))
        max_daily_change_7d = to_float(fund.get("max_daily_change_7d"))
        drawdown_30d = to_float(fund.get("drawdown_30d"))
        trend_7d = str(fund.get("trend_7d", "unknown"))
        risk_level = classify_risk_level(
            change=change,
            max_daily_change_7d=max_daily_change_7d,
            drawdown_30d=drawdown_30d,
            trend_7d=trend_7d,
        )
        enriched.append(
            {
                **fund,
                "risk_level": risk_level,
                "change_summary": build_change_summary(
                    change=change,
                    risk_level=risk_level,
                    max_daily_change_7d=max_daily_change_7d,
                    drawdown_30d=drawdown_30d,
                    trend_7d=trend_7d,
                ),
            }
        )
    return enriched


def classify_risk_level(
    change: float,
    max_daily_change_7d: float | None,
    drawdown_30d: float | None,
    trend_7d: str,
) -> str:
    absolute_change = abs(change)
    if (
        absolute_change >= 3
        or (max_daily_change_7d is not None and max_daily_change_7d >= 3)
        or (drawdown_30d is not None and drawdown_30d <= -8)
    ):
        return "high"
    if (
        absolute_change >= 1
        or (max_daily_change_7d is not None and max_daily_change_7d >= 1.5)
        or (drawdown_30d is not None and drawdown_30d <= -4)
        or trend_7d == "down"
    ):
        return "medium"
    return "low"


def build_change_summary(
    change: float,
    risk_level: str,
    max_daily_change_7d: float | None,
    drawdown_30d: float | None,
    trend_7d: str,
) -> str:
    if change > 0:
        direction = "上涨"
    elif change < 0:
        direction = "下跌"
    else:
        direction = "持平"

    volatility = (
        f"近 7 日最大单日波动 {max_daily_change_7d:.2f}%"
        if max_daily_change_7d is not None
        else "近 7 日波动数据不足"
    )
    drawdown = (
        f"近 30 日最大回撤 {drawdown_30d:.2f}%"
        if drawdown_30d is not None
        else "近 30 日回撤数据不足"
    )
    return (
        f"今日净值{direction} {abs(change):.2f}%，"
        f"7 日趋势为 {trend_7d}，{volatility}，{drawdown}，"
        f"基础波动风险等级为 {risk_level}。"
    )


def to_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None
