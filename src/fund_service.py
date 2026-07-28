from __future__ import annotations

from src.data_loader import load_funds
from src.fund_snapshot_store import (
    enrich_funds_with_snapshot_comparison,
    load_latest_snapshots_by_code,
)
from src.risk_analyzer import enrich_funds_with_risk
from src.watchlist_loader import normalize_fund_code


def lookup_fund(
    fund_code: object,
    use_real_data: bool = True,
) -> dict[str, object]:
    normalized_code = normalize_fund_code(fund_code)
    funds, data_source, warnings = load_funds(
        selected_codes=[normalized_code],
        prefer_real_data=use_real_data,
    )
    if not funds:
        raise LookupError(f"Fund code not found: {normalized_code}")

    funds = enrich_funds_with_risk(funds)
    previous_snapshots = load_latest_snapshots_by_code()
    funds = enrich_funds_with_snapshot_comparison(
        funds=funds,
        previous_snapshots=previous_snapshots,
    )

    return {
        "fund": funds[0],
        "data_source": data_source,
        "warnings": warnings,
    }
