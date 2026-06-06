from __future__ import annotations

from datetime import date

from src.report_template import build_markdown_report


def build_report(
    funds: list[dict[str, object]],
    report_date: date,
    history_comparison: dict[str, object] | None = None,
) -> str:
    return build_markdown_report(
        funds=funds,
        report_date=report_date,
        history_comparison=history_comparison,
    )
