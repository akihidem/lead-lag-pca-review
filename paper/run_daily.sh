#!/usr/bin/env bash
# Daily PAPER-trade run (PAPER ONLY — no broker, no capital).
# Cron (JST): 30 7 * * 1-5  -> runs after the US close (~06:00 JST) and before the
# TSE open (09:00 JST), so it books yesterday's completed trade and emits today's target.
set -euo pipefail
DIR="/home/muko1/Projects/lead-lag-pca-review"
cd "$DIR"
mkdir -p paper/logs
LOG="paper/logs/$(date +%Y-%m).log"
echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') =====" >> "$LOG"
"$DIR/.venv/bin/python" paper/trader.py >> "$LOG" 2>&1
