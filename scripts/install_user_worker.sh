#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_TEMPLATE="${PROJECT_DIR}/deploy/systemd/user/funds-agent-report-worker.service.template"
SERVICE_TARGET="${USER_SYSTEMD_DIR}/funds-agent-report-worker.service"
DEFAULT_PYTHON="/home/ago/.conda/envs/fund/bin/python"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "${DEFAULT_PYTHON}" ]]; then
    PYTHON_BIN="${DEFAULT_PYTHON}"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

mkdir -p "${USER_SYSTEMD_DIR}"
sed \
  -e "s|@PROJECT_DIR@|${PROJECT_DIR}|g" \
  -e "s|@PYTHON_BIN@|${PYTHON_BIN}|g" \
  "${SERVICE_TEMPLATE}" > "${SERVICE_TARGET}"

systemctl --user daemon-reload
systemctl --user enable --now funds-agent-report-worker.service

echo "Installed user worker service: funds-agent-report-worker.service"
echo "User unit directory: ~/.config/systemd/user"
echo "Python: ${PYTHON_BIN}"
echo "Check status: systemctl --user status funds-agent-report-worker.service"
echo "Check logs: journalctl --user -u funds-agent-report-worker.service -n 80 --no-pager"
