#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_TEMPLATE="${PROJECT_DIR}/deploy/systemd/user/funds-agent-daily-report.service.template"
TIMER_SOURCE="${PROJECT_DIR}/deploy/systemd/user/funds-agent-daily-report.timer"
SERVICE_TARGET="${USER_SYSTEMD_DIR}/funds-agent-daily-report.service"
TIMER_TARGET="${USER_SYSTEMD_DIR}/funds-agent-daily-report.timer"

mkdir -p "${USER_SYSTEMD_DIR}"
sed "s|@PROJECT_DIR@|${PROJECT_DIR}|g" "${SERVICE_TEMPLATE}" > "${SERVICE_TARGET}"
cp "${TIMER_SOURCE}" "${TIMER_TARGET}"

chmod +x "${PROJECT_DIR}/scripts/run_daily_report.sh"
systemctl --user daemon-reload
systemctl --user enable --now funds-agent-daily-report.timer

echo "Installed user timer: funds-agent-daily-report.timer"
echo "User unit directory: ~/.config/systemd/user"
echo "Check status: systemctl --user status funds-agent-daily-report.timer"
echo "Check logs: journalctl --user -u funds-agent-daily-report.service -n 80 --no-pager"
