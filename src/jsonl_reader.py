from __future__ import annotations

import json
from pathlib import Path


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, object]]:
    if not path.exists():
        return []

    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if limit is None:
        return records
    return records[-limit:]
