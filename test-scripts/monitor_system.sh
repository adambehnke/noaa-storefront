#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - System Monitoring Dashboard
# Real-time monitoring of AI multi-pond query system
#
# Usage: ./monitor_system.sh [--continuous] [--errors-only]
#
# Options:
#   --continuous    Refresh every 30 seconds
#   --errors-only   Only show errors and warnings
#
# Author: NOAA Federated Data Lake Team
###############################################################################

# Configuration
ENV="dev"
LAMBDA_NAME="noaa-enhanced-handler-dev"
REGION="us-east-1"
CONTINUOUS=false
ERRORS_ONLY=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --continuous)
      CONTINUOUS=true
      shift
      ;;
    --errors-only)
      ERRORS_ONLY=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--continuous] [--errors-only]"
      echo ""
      echo "Options:"
      echo "  --continuous    Refresh every 30 seconds"
      echo "  --errors-only   Only show errors and warnings"
      echo "  --help          Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

show_dashboard() {
  clear

  echo -e "${BLUE}"
  cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║              NOAA Federated Data Lake - System Monitor                   ║
║                      AI Multi-Pond Query System                           ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
  echo -e "${NC}"

  echo -e "${CYAN}Environment:${NC} $ENV"
  echo -e "${CYAN}Lambda:${NC}      $LAMBDA_NAME"
  echo -e "${CYAN}Time:${NC}        $(date '+%Y-%m-%d %H:%M:%S')"
  echo ""

  # Lambda Status
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}LAMBDA FUNCTION STATUS${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"

  LAMBDA_INFO=$(aws lambda get-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --region "$REGION" 2>&1)

  if [ $? -eq 0 ]; then
    STATE=$(echo "$LAMBDA_INFO" | jq -r '.State' 2>/dev/null || echo "Unknown")
    LAST_UPDATE=$(echo "$LAMBDA_INFO" | jq -r '.LastUpdateStatus' 2>/dev/null || echo "Unknown")
    MEMORY=$(echo "$LAMBDA_INFO" | jq -r '.MemorySize' 2>/dev/null || echo "Unknown")
    TIMEOUT=$(echo "$LAMBDA_INFO" | jq -r '.Timeout' 2>/dev/null || echo "Unknown")

    if [ "$STATE" = "Active" ] && [ "$LAST_UPDATE" = "Successful" ]; then
      echo -e "  Status:        ${GREEN}● Active${NC}"
    else
      echo -e "  Status:        ${YELLOW}⚠ $STATE${NC}"
    fi

    echo -e "  Last Update:   $LAST_UPDATE"
    echo -e "  Memory:        ${MEMORY}MB"
    echo -e "  Timeout:       ${TIMEOUT}s"
  else
    echo -e "  ${RED}✗ Lambda not found or access denied${NC}"
  fi

  echo ""

  # Recent Metrics (last hour)
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}METRICS (Last Hour)${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"

  END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)
  START_TIME=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S 2>/dev/null)

  # Invocations
  INVOCATIONS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value="$LAMBDA_NAME" \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --period 3600 \
    --statistics Sum \
    --region "$REGION" 2>/dev/null | jq -r '.Datapoints[0].Sum // 0')

  # Errors
  ERRORS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --dimensions Name=FunctionName,Value="$LAMBDA_NAME" \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --period 3600 \
    --statistics Sum \
    --region "$REGION" 2>/dev/null | jq -r '.Datapoints[0].Sum // 0')

  # Duration
  AVG_DURATION=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value="$LAMBDA_NAME" \
    --start-time "$START_TIME" \
    --end-time "$END_TIME" \
    --period 3600 \
    --statistics Average \
    --region "$REGION" 2>/dev/null | jq -r '.Datapoints[0].Average // 0')

  echo -e "  Invocations:   ${GREEN}$INVOCATIONS${NC}"

  if [ "$ERRORS" -gt 0 ]; then
    echo -e "  Errors:        ${RED}$ERRORS${NC}"
  else
    echo -e "  Errors:        ${GREEN}$ERRORS${NC}"
  fi

  if [ "$AVG_DURATION" != "0" ]; then
    AVG_DURATION_MS=$(echo "$AVG_DURATION" | awk '{printf "%.0f", $1}')
    echo -e "  Avg Duration:  ${AVG_DURATION_MS}ms"
  else
    echo -e "  Avg Duration:  N/A"
  fi

  if [ "$INVOCATIONS" -gt 0 ]; then
    ERROR_RATE=$(echo "scale=2; ($ERRORS / $INVOCATIONS) * 100" | bc)
    if (( $(echo "$ERROR_RATE > 5" | bc -l) )); then
      echo -e "  Error Rate:    ${RED}${ERROR_RATE}%${NC}"
    else
      echo -e "  Error Rate:    ${GREEN}${ERROR_RATE}%${NC}"
    fi
  fi

  echo ""

  # Recent Logs
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}RECENT ACTIVITY (Last 10 minutes)${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"

  LOG_GROUP="/aws/lambda/$LAMBDA_NAME"

  # Get recent logs
  RECENT_LOGS=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --start-time $(($(date +%s) * 1000 - 600000)) \
    --region "$REGION" \
    --limit 50 2>/dev/null)

  if [ $? -eq 0 ]; then
    # Look for AI pond selections
    POND_SELECTIONS=$(echo "$RECENT_LOGS" | jq -r '.events[].message' 2>/dev/null | grep -i "AI selected" | tail -5)

    if [ ! -z "$POND_SELECTIONS" ]; then
      echo -e "${GREEN}Recent AI Pond Selections:${NC}"
      echo "$POND_SELECTIONS" | while read -r line; do
        echo "  • $line"
      done
      echo ""
    fi

    # Look for errors
    ERROR_LOGS=$(echo "$RECENT_LOGS" | jq -r '.events[].message' 2>/dev/null | grep -iE "error|exception|failed" | grep -v "0 errors" | tail -5)

    if [ ! -z "$ERROR_LOGS" ] || [ "$ERRORS_ONLY" = true ]; then
      if [ ! -z "$ERROR_LOGS" ]; then
        echo -e "${RED}Recent Errors/Warnings:${NC}"
        echo "$ERROR_LOGS" | while read -r line; do
          echo "  • $line"
        done
        echo ""
      else
        echo -e "${GREEN}✓ No errors in last 10 minutes${NC}"
        echo ""
      fi
    fi

    # Look for query completions
    if [ "$ERRORS_ONLY" = false ]; then
      QUERY_LOGS=$(echo "$RECENT_LOGS" | jq -r '.events[].message' 2>/dev/null | grep -i "Query completed" | tail -5)

      if [ ! -z "$QUERY_LOGS" ]; then
        echo -e "${GREEN}Recent Query Completions:${NC}"
        echo "$QUERY_LOGS" | while read -r line; do
          echo "  • $line"
        done
        echo ""
      fi
    fi

    # Count unique queries
    QUERY_COUNT=$(echo "$RECENT_LOGS" | jq -r '.events[].message' 2>/dev/null | grep -i "Processing query" | wc -l | xargs)
    if [ "$QUERY_COUNT" -gt 0 ]; then
      echo -e "  Total queries processed: ${GREEN}$QUERY_COUNT${NC}"
      echo ""
    fi

  else
    echo -e "  ${YELLOW}⚠ Could not fetch logs${NC}"
    echo ""
  fi

  # Ingestion Status
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}DATA INGESTION STATUS${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"

  # Check oceanic ingestion (the only one scheduled currently)
  OCEANIC_LAMBDA="noaa-ingest-oceanic-dev"

  if aws lambda get-function --function-name "$OCEANIC_LAMBDA" --region "$REGION" > /dev/null 2>&1; then
    OCEANIC_INVOCATIONS=$(aws cloudwatch get-metric-statistics \
      --namespace AWS/Lambda \
      --metric-name Invocations \
      --dimensions Name=FunctionName,Value="$OCEANIC_LAMBDA" \
      --start-time "$START_TIME" \
      --end-time "$END_TIME" \
      --period 3600 \
      --statistics Sum \
      --region "$REGION" 2>/dev/null | jq -r '.Datapoints[0].Sum // 0')

    echo -e "  Oceanic Pond:  ${GREEN}● Active${NC} ($OCEANIC_INVOCATIONS ingestions/hour)"
  else
    echo -e "  Oceanic Pond:  ${YELLOW}○ Not deployed${NC}"
  fi

  echo -e "  Atmospheric:   ${YELLOW}○ Not deployed${NC} (using real-time API)"
  echo -e "  Buoy:          ${YELLOW}○ Not deployed${NC} (using real-time API)"
  echo -e "  Climate:       ${YELLOW}○ Not deployed${NC} (using real-time API)"

  echo ""

  # Quick Actions
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}QUICK ACTIONS${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
  echo ""
  echo "  View live logs:       aws logs tail $LOG_GROUP --follow"
  echo "  Re-deploy:            ./deployment/deploy_ai_system.sh"
  echo "  Run tests:            ./test-scripts/test_ai_queries.sh"
  echo "  Check schedules:      cd ingestion-scheduler && python3 schedule_all_ingestions.py --action status --env dev"
  echo ""

  if [ "$CONTINUOUS" = true ]; then
    echo -e "${YELLOW}Refreshing in 30 seconds... (Ctrl+C to stop)${NC}"
  fi
}

# Main loop
if [ "$CONTINUOUS" = true ]; then
  while true; do
    show_dashboard
    sleep 30
  done
else
  show_dashboard
fi
