from __future__ import annotations

import os
from datetime import date
from openai import OpenAI


def is_llm_available() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def build_llm_report(
    funds: list[dict[str, object]],
    report_date: date,
    history_comparison: dict[str, object] | None = None,
) -> str:

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    prompt = build_prompt(
        funds=funds,
        report_date=report_date,
        history_comparison=history_comparison,
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "You are a beginner-friendly fund research assistant.",
            },
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )

    content = response.choices[0].message.content
    return content.strip() if content else ""


def build_prompt(
    funds: list[dict[str, object]],
    report_date: date,
    history_comparison: dict[str, object] | None = None,
) -> str:
    fund_lines: list[str] = []
    for fund in funds:
        snapshot_comparison = fund.get("snapshot_comparison", {})
        snapshot_summary = (
            str(snapshot_comparison.get("summary"))
            if isinstance(snapshot_comparison, dict)
            else "No snapshot comparison available."
        )
        fund_lines.append(
            (
                f"- Fund Name: {fund['fund_name']}, "
                f"Fund Code: {fund['fund_code']}, "
                f"Theme: {fund['theme']}, "
                f"NAV: {fund['nav']}, "
                f"NAV Date: {fund.get('nav_date', 'unknown')}, "
                f"Daily Change: {fund['daily_change_percent']}%, "
                f"Risk Level: {fund.get('risk_level', 'unknown')}, "
                f"Change Summary: {fund.get('change_summary', 'No summary')}, "
                f"Snapshot Comparison: {snapshot_summary}"
            )
        )

    fund_block = "\n".join(fund_lines) if fund_lines else "- No fund data available."
    history_summary = (
        str(history_comparison.get("summary"))
        if history_comparison
        else "No previous report comparison available."
    )

    return f"""
Write a short daily markdown report for {report_date.isoformat()} using the fund data below.

Requirements:
- Use markdown.
- Keep the report concise and easy to understand.
- For each fund, include NAV date, daily change, risk level, and a short explanation.
- Include each fund's snapshot comparison when available.
- Include a brief history comparison section using the provided history summary.
- Clearly explain that the risk level is a simple rule-based signal, not a professional risk rating.
- Mention that the content is for learning and informational use only.
- Do not give direct buy or sell instructions.

History summary:
{history_summary}

Fund data:
{fund_block}
""".strip()
