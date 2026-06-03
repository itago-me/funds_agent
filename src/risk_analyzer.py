from __future__ import annotations


def enrich_funds_with_risk(funds: list[dict[str, object]]) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for fund in funds:
        change = float(str(fund.get("daily_change_percent", 0)))
        risk_level = classify_risk_level(change)
        enriched.append(
            {
                **fund,
                "risk_level": risk_level,
                "change_summary": build_change_summary(change=change, risk_level=risk_level),
            }
        )
    return enriched


def classify_risk_level(change: float) -> str:
    absolute_change = abs(change)
    if absolute_change >= 3:
        return "high"
    if absolute_change >= 1:
        return "medium"
    return "low"


def build_change_summary(change: float, risk_level: str) -> str:
    if change > 0:
        direction = "上涨"
    elif change < 0:
        direction = "下跌"
    else:
        direction = "持平"

    return f"今日净值{direction} {abs(change):.2f}%，基础波动风险等级为 {risk_level}。"
