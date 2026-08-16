# Funds Agent Worker Service

This project can process asynchronous report tasks through a long-running user-level systemd service.

## Manual Run

Run the worker directly when developing:

```bash
python -m src.report_worker_cli
```

Process one queued task and exit:

```bash
python -m src.report_worker_cli --once
```

## Install User Service

Install and start the worker service:

```bash
./scripts/install_user_worker.sh
```

The installed unit is:

```text
~/.config/systemd/user/funds-agent-report-worker.service
```

## Manage Service

Check status:

```bash
systemctl --user status funds-agent-report-worker.service
```

Restart:

```bash
systemctl --user restart funds-agent-report-worker.service
```

Follow logs:

```bash
journalctl --user -u funds-agent-report-worker.service -f
```

Uninstall:

```bash
./scripts/uninstall_user_worker.sh
```
