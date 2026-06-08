# Scheduling

This document explains how to run Funds Agent as a daily scheduled task.

## What The Scheduled Task Does

The scheduled task runs the same script you already tested manually:

```bash
./scripts/run_daily_report.sh
```

That script runs:

```bash
python main.py --use-watchlist --use-real-data --use-llm
```

After each run, the project should produce or update:

- `reports/daily_report_<date>.md`
- `reports/index.jsonl`
- `data/fund_snapshots.jsonl`
- `logs/task_runs.jsonl`
- `logs/cron.log` if cron output redirection is configured

## Recommended Cron Setup

Open your crontab:

```bash
crontab -e
```

Add this line to run every weekday at 09:00:

```cron
0 9 * * 1-5 /home/ago/items/funds_agent/scripts/run_daily_report.sh >> /home/ago/items/funds_agent/logs/cron.log 2>&1
```

If you want to run every day at 09:00 instead:

```cron
0 9 * * * /home/ago/items/funds_agent/scripts/run_daily_report.sh >> /home/ago/items/funds_agent/logs/cron.log 2>&1
```

A copyable template is also available at:

```text
scripts/cron.example
```

## Verify The Script First

Before adding cron, run the script manually:

```bash
./scripts/run_daily_report.sh
```

Then check:

```bash
tail -n 5 logs/task_runs.jsonl
tail -n 5 reports/index.jsonl
```

If the task succeeds manually but fails in cron, the most common cause is environment difference.

## Environment Notes

Cron runs in a smaller shell environment than your terminal. The script changes into the project root before running Python, so `.env` can still be loaded by the application.

Make sure these are true:

- `scripts/run_daily_report.sh` is executable.
- `.env` exists in the project root if DeepSeek is used.
- Python dependencies are installed in the Python environment used by cron.
- The cron command uses the correct absolute project path.

If your dependencies are installed in a virtual environment, update `scripts/run_daily_report.sh` to call that Python explicitly, for example:

```bash
/home/ago/items/funds_agent/.venv/bin/python main.py --use-watchlist --use-real-data --use-llm
```

## Check Results

Cron terminal output goes here if you use the recommended redirection:

```bash
tail -n 50 logs/cron.log
```

Application task status goes here:

```bash
tail -n 10 logs/task_runs.jsonl
```

Generated reports are stored in:

```text
reports/
```

Fund data snapshots are stored in:

```text
data/fund_snapshots.jsonl
```

## Disable The Task

Open crontab:

```bash
crontab -e
```

Then delete or comment out the Funds Agent line:

```cron
# 0 9 * * 1-5 /home/ago/items/funds_agent/scripts/run_daily_report.sh >> /home/ago/items/funds_agent/logs/cron.log 2>&1
```
