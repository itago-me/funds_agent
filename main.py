from __future__ import annotations

import argparse
from datetime import date

from dotenv import load_dotenv

from src.data_loader import load_funds
from src.llm_analyzer import build_llm_report, is_llm_available
from src.report_writer import write_report
from src.simple_analyzer import build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a simple fund daily report.")
    parser.add_argument(
        "--codes",
        nargs="*",
        help="Optional fund codes to include in the report, for example: --codes 000001 000002",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use the DeepSeek model to generate the report when DEEPSEEK_API_KEY is set.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    report_date = date.today()
    funds = load_funds(selected_codes=args.codes)

    if args.use_llm and is_llm_available():
        report = build_llm_report(funds=funds, report_date=report_date)
        print("analysis mode: deepseek llm")
    else:
        report = build_report(funds=funds, report_date=report_date)
        if args.use_llm:
            print("analysis mode: fallback rule mode (missing DEEPSEEK_API_KEY)")
        else:
            print("analysis mode: rule mode")

    report_path = write_report(content=report, report_date=report_date)
    print("今日基金分析报道:")
    print(report)
    print(f"Report created: {report_path}")


if __name__ == "__main__":
    main()
