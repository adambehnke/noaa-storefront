#!/bin/bash
#
# Real-time Backfill Monitor
# Shows live progress of historical data ingestion
#

export AWS_PROFILE=noaa-target

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear

while true; do
    clear
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     NOAA Historical Backfill - Live Monitor                 ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Check if process is running
    if [ -f backfill.pid ]; then
        PID=$(cat backfill.pid)
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${GREEN}Status: RUNNING (PID: ${PID})${NC}"
        else
            echo -e "${YELLOW}Status: STOPPED (check logs for completion or errors)${NC}"
        fi
    else
        echo -e "${YELLOW}Status: NO PID FILE FOUND${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}Progress Checkpoint:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    
    if [ -f backfill_checkpoint.json ]; then
        python3 <<EOF
import json
try:
    with open('backfill_checkpoint.json', 'r') as f:
        data = json.load(f)
    
    print(f"Started: {data.get('started_at', 'N/A')}")
    print(f"Last Updated: {data.get('last_updated', 'N/A')}")
    print(f"Total Records: {data.get('total_records', 0):,}")
    print(f"Total API Calls: {data.get('total_api_calls', 0):,}")
    print("")
    
    for pond, pdata in data.get('ponds', {}).items():
        completed = len(pdata.get('completed_ranges', []))
        failed = len(pdata.get('failed_ranges', []))
        records = pdata.get('total_records', 0)
        print(f"{pond.upper():15} | Records: {records:>8,} | Completed: {completed:>3} | Failed: {failed:>2}")
    
except Exception as e:
    print(f"Error reading checkpoint: {e}")
EOF
    else
        echo "No checkpoint file found yet"
    fi
    
    echo ""
    echo -e "${BLUE}Recent Log Entries:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    
    LOG_FILE=$(ls -t backfill_*.log 2>/dev/null | head -1)
    if [ -n "$LOG_FILE" ]; then
        tail -10 "$LOG_FILE" | grep -E "INFO|ERROR|WARNING" | tail -5
    else
        echo "No log file found"
    fi
    
    echo ""
    echo -e "${BLUE}Current Bronze Layer Size:${NC}"
    echo "─────────────────────────────────────────────────────────────"
    
    SIZE=$(aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/ --recursive --summarize 2>/dev/null | grep "Total Size" | awk '{print $3}')
    if [ -n "$SIZE" ]; then
        SIZE_GB=$(echo "scale=2; $SIZE / 1073741824" | bc 2>/dev/null || echo "N/A")
        echo "Bronze Layer: ${SIZE_GB} GB"
    fi
    
    echo ""
    echo -e "${CYAN}Press Ctrl+C to exit monitor${NC}"
    echo -e "${CYAN}Refresh: 10 seconds${NC}"
    
    sleep 10
done
