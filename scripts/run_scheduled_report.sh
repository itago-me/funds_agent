#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Keep the report result authoritative even if the optional notification fails.
set +e
/home/ago/.conda/envs/fund/bin/python main.py --use-watchlist --use-real-data
REPORT_EXIT_CODE=$?
set -e

/home/ago/.conda/envs/fund/bin/python -m src.notification_service --latest || true

exit ${REPORT_EXIT_CODE}
