from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def normalize_report_path_for_storage(report_path: Path | str) -> str:
    path = Path(report_path)
    if path.is_relative_to(BASE_DIR):
        return path.relative_to(BASE_DIR).as_posix()
    return path.as_posix() if not path.is_absolute() else str(path)


def normalize_report_path_for_migration(report_path: str) -> str:
    path = Path(report_path)
    if path.is_relative_to(BASE_DIR):
        return path.relative_to(BASE_DIR).as_posix()

    parts = path.parts
    if path.is_absolute() and "reports" in parts:
        return Path(*parts[parts.index("reports") :]).as_posix()

    return path.as_posix() if not path.is_absolute() else str(path)


def resolve_report_path(report_path: str) -> Path:
    path = Path(report_path)
    if not report_path:
        return path

    if path.is_relative_to(BASE_DIR):
        return path

    base_dir_str = str(BASE_DIR.resolve())
    parts = path.parts
    if path.is_absolute() and not str(path).startswith(base_dir_str) and "reports" in parts:
        candidate = BASE_DIR.joinpath(*parts[parts.index("reports") :])
        if "funds_agent" in parts or candidate.exists():
            return candidate

    if path.exists():
        return path

    if "reports" in parts:
        candidate = BASE_DIR.joinpath(*parts[parts.index("reports") :])
        if candidate.exists():
            return candidate

    return path
