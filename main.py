from __future__ import annotations

import argparse
from datetime import date

from src.data_loader import load_funds
from src.report_writer import write_report
from src.simple_analyzer import build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a simple fund daily report.")
    parser.add_argument(
        "--codes",
        nargs="*",
        help="Optional fund codes to include in the report, for example: --codes 000001 000002",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_date = date.today()
    funds = load_funds(selected_codes=args.codes)
    report = build_report(funds=funds, report_date=report_date)
    report_path = write_report(content=report, report_date=report_date)
    print("今日基金分析报道:", report)
    print(f"Report created: {report_path}")


if __name__ == "__main__":
    main()
