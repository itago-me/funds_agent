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
scripts/run_daily_report.sh
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
