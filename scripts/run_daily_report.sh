# !usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

python main.py --use-watchlist --use-real-data --use-llm
