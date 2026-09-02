from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.data_loader import load_funds
from src.fund_snapshot_store import (
    append_fund_snapshots,
    enrich_funds_with_snapshot_comparison,
    load_latest_snapshots_by_code,
)
from src.llm_analyzer import build_llm_report, is_llm_available
from src.report_index import (
    append_report_index,
    build_history_comparison,
    load_latest_report_record,
)
from src.report_writer import write_report
from src.risk_analyzer import enrich_funds_with_risk
from src.simple_analyzer import build_report
from src.task_logger import finish_task_failed, finish_task_success, start_task
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


def run_daily_report(
    *,
    codes: list[str] | None = None,
    use_llm: bool = False,
    use_real_data: bool = False,
    use_watchlist: bool = False,
    user_id: int | None = None,
) -> dict[str, object]:
    from dotenv import load_dotenv

    load_dotenv()
    report_date = date.today()
    selected_codes = codes
    if selected_codes is None and use_watchlist:
        selected_codes = load_watchlist_codes(user_id=user_id)
    funds, data_source, warnings = load_funds(
        selected_codes=selected_codes,
        prefer_real_data=use_real_data,
    )
    funds = enrich_funds_with_risk(funds)
    previous_snapshots = load_latest_snapshots_by_code(user_id=user_id)
    funds = enrich_funds_with_snapshot_comparison(
        funds=funds,
        previous_snapshots=previous_snapshots,
    )

    analysis_mode = "rule"
    previous_record = load_latest_report_record(user_id=user_id)
    if use_llm and is_llm_available():
        try:
            analysis_mode = "deepseek_llm"
            history_comparison = build_history_comparison(
                previous_record=previous_record,
                current_data_source=data_source,
                current_analysis_mode=analysis_mode,
                current_fund_codes=selected_codes,
                current_warnings=warnings,
            )
            report = build_llm_report(
                funds=funds,
                report_date=report_date,
                history_comparison=history_comparison,
            )
            print("analysis mode: deepseek llm")
        except Exception as exc:
            warnings.append(f"DeepSeek request failed. Falling back to rule mode: {exc}")
            analysis_mode = "rule_fallback"
            history_comparison = build_history_comparison(
                previous_record=previous_record,
                current_data_source=data_source,
                current_analysis_mode=analysis_mode,
                current_fund_codes=selected_codes,
                current_warnings=warnings,
            )
            report = build_report(
                funds=funds,
                report_date=report_date,
                history_comparison=history_comparison,
            )
            print("analysis mode: fallback rule mode (DeepSeek request failed)")
    else:
        if use_llm:
            analysis_mode = "rule_fallback"
            print("analysis mode: fallback rule mode (missing DEEPSEEK_API_KEY)")
        else:
            print("analysis mode: rule mode")
        history_comparison = build_history_comparison(
            previous_record=previous_record,
            current_data_source=data_source,
            current_analysis_mode=analysis_mode,
            current_fund_codes=selected_codes,
            current_warnings=warnings,
        )
        report = build_report(
            funds=funds,
            report_date=report_date,
            history_comparison=history_comparison,
        )

    print(f"data source: {data_source}")
    if selected_codes:
        print(f"fund codes: {', '.join(selected_codes)}")
    for warning in warnings:
        print(f"warning: {warning}")
    report_path = write_report(
        content=report,
        report_date=report_date,
        user_id=user_id,
    )
    append_fund_snapshots(
        funds=funds,
        report_date=report_date.isoformat(),
        data_source=data_source,
        user_id=user_id,
    )
    append_report_index(
        report_path=report_path,
        report_date=report_date.isoformat(),
        data_source=data_source,
        analysis_mode=analysis_mode,
        fund_codes=selected_codes,
        warnings=warnings,
        history_comparison=history_comparison,
        user_id=user_id,
    )
    print("今日基金分析报道:")
    print(report)
    print(f"Report created: {report_path}")
    return {
        "report_date": report_date.isoformat(),
        "data_source": data_source,
        "analysis_mode": analysis_mode,
        "fund_codes": selected_codes,
        "report_path": str(report_path),
        "warnings": warnings,
        "report_content": report,
    }


def main() -> None:
    args = parse_args()
    selected_codes = resolve_fund_codes(args)
    task = start_task(
        run_options={
            "codes": selected_codes,
            "use_watchlist": args.use_watchlist,
            "use_real_data": args.use_real_data,
            "use_llm": args.use_llm,
        },
        user_id=None,
    )
    try:
        result = run_daily_report(
            codes=selected_codes,
            use_llm=args.use_llm,
            use_real_data=args.use_real_data,
            use_watchlist=args.use_watchlist,
        )
    except Exception as exc:
        finish_task_failed(task=task, error=exc)
        raise

    finish_task_success(
        task=task,
        data_source=str(result["data_source"]),
        analysis_mode=str(result["analysis_mode"]),
        fund_codes=result["fund_codes"] if isinstance(result["fund_codes"], list) else None,
        report_path=Path(str(result["report_path"])),
        warnings=result["warnings"] if isinstance(result["warnings"], list) else [],
    )


if __name__ == "__main__":
    main()
