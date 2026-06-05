from __future__ import annotations

from datetime import date


def build_report(
    funds: list[dict[str, object]],
    report_date: date,
    history_comparison: dict[str, object] | None = None,
) -> str:
    lines = [
        f"# Fund Daily Report - {report_date.isoformat()}",
        "",
        "> This report is for learning and informational use only. It is not investment advice.",
        "",
    ]
    if history_comparison:
        lines.extend(
            [
                "## History Comparison",
                f"- {history_comparison.get('summary', 'No comparison available.')}",
                "",
            ]
        )

    if not funds:
        lines.extend(
            [
                "## No Funds Found",
                "- No matching fund codes were found in the sample data.",
                "",
            ]
        )
        return "\n".join(lines)

    for fund in funds:
        name = str(fund["fund_name"])
        code = str(fund["fund_code"])
        nav = str(fund["nav"])
        change = float(str(fund["daily_change_percent"]))
        theme = str(fund["theme"])
        nav_date = str(fund.get("nav_date", report_date.isoformat()))
        risk_level = str(fund.get("risk_level", "unknown"))
        change_summary = str(fund.get("change_summary", "No change summary available."))
        direction = "rose" if change >= 0 else "fell"

        lines.extend(
            [
                f"## {name} ({code})",
                f"- Theme: {theme}",
                f"- Latest NAV: {nav}",
                f"- NAV Date: {nav_date}",
                f"- Daily Change: {change:.2f}%",
                f"- Risk Level: {risk_level}",
                f"- Change Summary: {change_summary}",
                (
                    f"- Simple Analysis: {name} {direction} {abs(change):.2f}% today. "
                    "Review the NAV date and risk level before drawing conclusions."
                ),
                "",
            ]
        )

    return "\n".join(lines)
