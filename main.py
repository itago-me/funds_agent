from __future__ import annotations

import argparse
from datetime import date

from dotenv import load_dotenv

from src.data_loader import load_funds
from src.llm_analyzer import build_llm_report, is_llm_available
from src.report_writer import write_report
from src.risk_analyzer import enrich_funds_with_risk
from src.simple_analyzer import build_report
from src.watchlist_loader import load_watchlist_codes


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
    parser.add_argument(
        "--use-real-data",
        action="store_true",
        help="Try to load real fund data from AkShare. Falls back to sample data if unavailable.",
    )
    parser.add_argument(
        "--use-watchlist",
        action="store_true",
        help="Load fund codes from watchlist.json when --codes is not provided.",
    )
    return parser.parse_args()


def resolve_fund_codes(args: argparse.Namespace) -> list[str] | None:
    if args.codes:
        return args.codes
    if args.use_watchlist:
        return load_watchlist_codes()
    return None


def main() -> None:
    load_dotenv()
    args = parse_args()
    report_date = date.today()
    selected_codes = resolve_fund_codes(args)
    funds, data_source, warnings = load_funds(
        selected_codes=selected_codes,
        prefer_real_data=args.use_real_data,
    )
    funds = enrich_funds_with_risk(funds)

    if args.use_llm and is_llm_available():
        try:
            report = build_llm_report(funds=funds, report_date=report_date)
            print("analysis mode: deepseek llm")
        except Exception as exc:
            warnings.append(f"DeepSeek request failed. Falling back to rule mode: {exc}")
            report = build_report(funds=funds, report_date=report_date)
            print("analysis mode: fallback rule mode (DeepSeek request failed)")
    else:
        report = build_report(funds=funds, report_date=report_date)
        if args.use_llm:
            print("analysis mode: fallback rule mode (missing DEEPSEEK_API_KEY)")
        else:
            print("analysis mode: rule mode")

    print(f"data source: {data_source}")
    if selected_codes:
        print(f"fund codes: {', '.join(selected_codes)}")
    for warning in warnings:
        print(f"warning: {warning}")
    report_path = write_report(content=report, report_date=report_date)
    print("今日基金分析报道:")
    print(report)
    print(f"Report created: {report_path}")


if __name__ == "__main__":
    main()
