# User Systemd Timer

This project can run the daily fund report through a user-level systemd timer.

## Install

```bash
./scripts/install_user_timer.sh
```

The installer writes these user units:

```text
~/.config/systemd/user/funds-agent-daily-report.service
~/.config/systemd/user/funds-agent-daily-report.timer
```

The timer runs every weekday at 09:00 and uses:

```bash
scripts/run_scheduled_report.sh
```

The scheduled wrapper runs the report first and then sends a desktop
notification through `notify-send`. The report exit code remains authoritative:
if notification delivery fails, the wrapper does not change the report result.

The notification action opens a URL in this form:

```text
http://127.0.0.1:8001/?report_id=<report-id>
```

The dashboard reads `report_id` from the URL and loads the existing
`GET /reports/{report_id}` endpoint.

For a manual notification preview without displaying a desktop notification:

```bash
FUNDS_AGENT_NOTIFY_DRY_RUN=1 \
  /home/ago/.conda/envs/fund/bin/python -m src.notification_service --latest
```

## Check Status

```bash
systemctl --user status funds-agent-daily-report.timer
systemctl --user list-timers funds-agent-daily-report.timer
journalctl --user -u funds-agent-daily-report.service -n 80 --no-pager
```

Application-level run records are still written to:

```text
logs/task_runs.jsonl
```

## Uninstall

```bash
./scripts/uninstall_user_timer.sh
```
