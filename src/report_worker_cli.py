"""Command-line entrypoint for the Redis report worker."""

from __future__ import annotations

import argparse
from typing import Any, Callable

from src.report_worker import process_next_report_task, run_report_worker


WorkerRunner = Callable[..., None]
ProcessRunner = Callable[..., dict[str, object] | None]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Funds Agent Redis report worker.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Seconds to wait before checking the Redis queue again.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued task and exit.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    worker_runner: WorkerRunner = run_report_worker,
    process_runner: ProcessRunner = process_next_report_task,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.once:
            process_runner()
            return 0
        worker_runner(poll_interval_seconds=args.poll_interval)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
