from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = BASE_DIR / "sample_data" / "funds.json"


def load_funds(selected_codes: list[str] | None = None) -> list[dict[str, object]]:
    with SAMPLE_DATA_PATH.open("r", encoding="utf-8") as file:
        funds: list[dict[str, object]] = json.load(file)

    if not selected_codes:
        return funds

    selected = set(selected_codes)
    return [fund for fund in funds if str(fund["fund_code"]) in selected]
