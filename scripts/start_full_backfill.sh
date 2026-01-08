#!/bin/bash
#
# Start Full Historical Backfill
# This will run for 24-36 hours to collect 1 year of data
#

export AWS_PROFILE=noaa-target
export AWS_REGION=us-east-1

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="backfill_365d_${TIMESTAMP}.log"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     NOAA Historical Backfill - FULL DEPLOYMENT              ║"
echo "║     Starting 365-day backfill for ALL ponds                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  - Account: 899626030376"
echo "  - Ponds: atmospheric, oceanic, buoy, climate, terrestrial"
echo "  - Days back: 365"
echo "  - Log file: ${LOG_FILE}"
echo "  - Checkpoint: backfill_checkpoint.json"
echo ""
echo "Starting backfill in 5 seconds..."
echo "Press Ctrl+C to cancel"
sleep 5

# Start backfill
nohup python3 scripts/historical_backfill_system.py \
  --ponds all \
  --days-back 365 \
  > "${LOG_FILE}" 2>&1 &

PID=$!
echo $PID > backfill.pid

echo ""
echo "✅ Backfill started!"
echo ""
echo "Process ID: ${PID}"
echo "Log file: ${LOG_FILE}"
echo "Checkpoint: backfill_checkpoint.json"
echo ""
echo "Monitor progress:"
echo "  tail -f ${LOG_FILE}"
echo "  cat backfill_checkpoint.json | python3 -m json.tool"
echo ""
echo "Check process:"
echo "  ps aux | grep $PID"
echo ""
echo "Stop backfill:"
echo "  kill $PID"
echo ""
