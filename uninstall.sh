#!/bin/bash

echo "[*] Uninstalling cron jobs for posture.py and alerts.py..."

# Backup existing crontab
crontab -l 2>/dev/null > backup_crontab.bak || true

# Remove lines with our job markers
crontab -l 2>/dev/null | grep -v "# posture_job" | grep -v "# alerts_job" > new_crontab || true

# Apply cleaned crontab
crontab new_crontab
rm new_crontab

echo "[✅] Crontab entries for posture.py and alerts.py removed."
echo "[*] Backup of previous crontab saved to backup_crontab.bak"
