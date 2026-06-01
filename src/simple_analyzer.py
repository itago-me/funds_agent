from __future__ import annotations

from datetime import date


def build_report(funds: list[dict[str, object]], report_date: date) -> str:
    lines = [
        f"# Fund Daily Report - {report_date.isoformat()}",
        "",
        "> This report is for learning and informational use only. It is not investment advice.",
        "",
    ]

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
        change = float(fund["daily_change_percent"])
        theme = str(fund["theme"])
        direction = "rose" if change >= 0 else "fell"

        lines.extend(
            [
                f"## {name} ({code})",
                f"- Theme: {theme}",
                f"- Latest NAV: {nav}",
                f"- Daily Change: {change:.2f}%",
                (
                    f"- Simple Analysis: {name} {direction} {abs(change):.2f}% today. "
                    "This version still uses rule-based text. "
                    "The next stage will replace this part with model-generated analysis."
                ),
                "",
            ]
        )

    return "\n".join(lines)
