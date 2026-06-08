#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

# /home/ago/.conda/envs/fund/bin/python main.py --use-watchlist --use-real-data --use-llm

/home/ago/.conda/envs/fund/bin/python main.py --use-watchlist --use-real-data
