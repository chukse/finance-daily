#!/usr/bin/env bash
# Daily pipeline entrypoint — this is what cron runs.
set -euo pipefail

PROJECT_DIR="/home/chuks/finance_daily"
cd "$PROJECT_DIR"

# Load API key (and any secrets) if a .env file exists.
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

mkdir -p "$PROJECT_DIR/data/logs"
LOG="$PROJECT_DIR/data/logs/$(date +%Y-%m-%d).log"

echo "===== run started $(date) =====" >> "$LOG"
"$PROJECT_DIR/.venv/bin/python" -m finance_daily.pipeline >> "$LOG" 2>&1
echo "===== run finished $(date) =====" >> "$LOG"
