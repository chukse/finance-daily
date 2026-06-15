#!/usr/bin/env bash
# Install the daily cron job (runs at 06:30 local time, Mon–Sat).
set -euo pipefail

PROJECT_DIR="/home/chuks/finance_daily"
RUN="$PROJECT_DIR/scripts/run_daily.sh"
CRON_LINE="30 6 * * 1-6 $RUN"

chmod +x "$RUN"

# Remove any existing entry for this script, then add fresh.
( crontab -l 2>/dev/null | grep -v -F "$RUN" ; echo "$CRON_LINE" ) | crontab -

echo "Installed cron job:"
echo "  $CRON_LINE"
echo
echo "NOTE: WSL must be running at 06:30 for this to fire."
echo "Verify with:  crontab -l"
echo "Make sure cron is running:  sudo service cron start"
