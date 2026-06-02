from __future__ import annotations

import os
from datetime import date
from openai import OpenAI


def is_llm_available() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def build_llm_report(funds: list[dict[str, object]], report_date: date) -> str:

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    prompt = build_prompt(funds=funds, report_date=report_date)

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


def build_prompt(funds: list[dict[str, object]], report_date: date) -> str:
    fund_lines: list[str] = []
    for fund in funds:
        fund_lines.append(
            (
                f"- Fund Name: {fund['fund_name']}, "
                f"Fund Code: {fund['fund_code']}, "
                f"Theme: {fund['theme']}, "
                f"NAV: {fund['nav']}, "
                f"Daily Change: {fund['daily_change_percent']}%"
            )
        )

    fund_block = "\n".join(fund_lines) if fund_lines else "- No fund data available."

    return f"""
Write a short daily markdown report for {report_date.isoformat()} using the fund data below.

Requirements:
- Use markdown.
- Keep the report concise and easy to understand.
- For each fund, include a short explanation of today's move.
- Mention that the content is for learning and informational use only.
- Do not give direct buy or sell instructions.

Fund data:
{fund_block}
""".strip()
