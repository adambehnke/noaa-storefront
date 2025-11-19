#!/bin/bash

################################################################################
# NOAA System Status Check
# Quick script to check current system health and data ingestion status
################################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
BUCKET_NAME="noaa-data-lake-${ENV}"
DATABASE_NAME="noaa_federated_${ENV}"
ATHENA_OUTPUT="s3://${BUCKET_NAME}/athena-results/"

PONDS=("atmospheric" "oceanic" "buoy" "climate" "spatial" "terrestrial")

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        NOAA Data Lake - System Status Check             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo -e "${CYAN}Environment: ${ENV}${NC}"
echo -e "${CYAN}Region: ${AWS_REGION}${NC}"
echo -e "${CYAN}Time: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

################################################################################
# 1. Check Lambda Functions
################################################################################

echo "=========================================="
echo "1. Lambda Functions Status"
echo "=========================================="
echo ""

for pond in "${PONDS[@]}"; do
    lambda_name="noaa-ingest-${pond}-${ENV}"

    if aws lambda get-function --function-name "${lambda_name}" --region "${AWS_REGION}" &>/dev/null; then
        # Get last execution from logs
        recent=$(aws logs filter-log-events \
            --log-group-name "/aws/lambda/${lambda_name}" \
            --start-time $(($(date +%s) * 1000 - 3600000)) \
            --filter-pattern "Ingestion complete" \
            --region "${AWS_REGION}" \
            --max-items 1 \
            --query 'events[0].message' \
            --output text 2>/dev/null)

        if [ -n "${recent}" ] && [ "${recent}" != "None" ]; then
            echo -e "${GREEN}✓ ${pond}${NC} - Active (recent execution found)"
            echo "  ${recent}" | grep -o '"bronze_records":[0-9]*' | sed 's/"bronze_records":/  Bronze: /' || true
        else
            echo -e "${YELLOW}⚠ ${pond}${NC} - No recent executions (waiting for schedule)"
        fi
    else
        echo -e "${RED}✗ ${pond}${NC} - Lambda not found!"
    fi
done

################################################################################
# 2. Check S3 Data
################################################################################

echo ""
echo "=========================================="
echo "2. S3 Data Storage"
echo "=========================================="
echo ""

# Check each layer
for layer in bronze silver gold; do
    echo "${layer^^} Layer:"

    file_count=$(aws s3 ls "s3://${BUCKET_NAME}/${layer}/" --recursive --region "${AWS_REGION}" 2>/dev/null | wc -l | tr -d ' ')

    if [ "${file_count}" -gt 0 ]; then
        total_size=$(aws s3 ls "s3://${BUCKET_NAME}/${layer}/" --recursive --human-readable --summarize --region "${AWS_REGION}" 2>/dev/null | grep "Total Size" | awk '{print $3" "$4}')
        echo -e "${GREEN}  ✓ ${file_count} files, ${total_size}${NC}"
    else
        echo -e "${RED}  ✗ No files found${NC}"
    fi
done

# Latest files
echo ""
echo "Latest Gold Layer Files:"
aws s3 ls "s3://${BUCKET_NAME}/gold/" --recursive --region "${AWS_REGION}" 2>/dev/null | sort -k1,2 -r | head -5 | awk '{print "  " $1" "$2" "$3" "$4}'

################################################################################
# 3. Check Athena Tables
################################################################################

echo ""
echo "=========================================="
echo "3. Athena Query Results"
echo "=========================================="
echo ""

query_table() {
    local table=$1

    # Start query
    query_id=$(aws athena start-query-execution \
        --query-string "SELECT COUNT(*) FROM ${table}" \
        --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
        --query-execution-context "Database=${DATABASE_NAME}" \
        --region "${AWS_REGION}" \
        --query 'QueryExecutionId' \
        --output text 2>/dev/null)

    if [ -z "${query_id}" ]; then
        echo -e "${RED}✗ ${table}${NC} - Query failed to start"
        return
    fi

    # Wait for result (max 10 seconds)
    for i in {1..10}; do
        status=$(aws athena get-query-execution \
            --query-execution-id "${query_id}" \
            --region "${AWS_REGION}" \
            --query 'QueryExecution.Status.State' \
            --output text 2>/dev/null)

        if [ "${status}" = "SUCCEEDED" ]; then
            result=$(aws athena get-query-results \
                --query-execution-id "${query_id}" \
                --region "${AWS_REGION}" \
                --query 'ResultSet.Rows[1].Data[0].VarCharValue' \
                --output text 2>/dev/null)

            if [ -n "${result}" ] && [ "${result}" != "0" ]; then
                echo -e "${GREEN}✓ ${table}${NC} - ${result} records"
            else
                echo -e "${YELLOW}⚠ ${table}${NC} - Table exists but no data yet"
            fi
            return
        elif [ "${status}" = "FAILED" ]; then
            echo -e "${RED}✗ ${table}${NC} - Query failed"
            return
        fi
        sleep 1
    done

    echo -e "${YELLOW}⚠ ${table}${NC} - Query timeout"
}

# Check main tables
query_table "atmospheric_observations_gold"
query_table "atmospheric_alerts_gold"
query_table "buoy_metadata_gold"
query_table "spatial_zones_gold"
query_table "terrestrial_observations_gold"

################################################################################
# 4. Check EventBridge Schedules
################################################################################

echo ""
echo "=========================================="
echo "4. EventBridge Schedules"
echo "=========================================="
echo ""

enabled_count=0
disabled_count=0

for pond in "${PONDS[@]}"; do
    lambda_name="noaa-ingest-${pond}-${ENV}"

    # Check incremental schedule
    incremental_rule="${lambda_name}-incremental"
    incremental_state=$(aws events describe-rule \
        --name "${incremental_rule}" \
        --region "${AWS_REGION}" \
        --query 'State' \
        --output text 2>/dev/null)

    # Check backfill schedule
    backfill_rule="${lambda_name}-backfill"
    backfill_state=$(aws events describe-rule \
        --name "${backfill_rule}" \
        --region "${AWS_REGION}" \
        --query 'State' \
        --output text 2>/dev/null)

    if [ "${incremental_state}" = "ENABLED" ] && [ "${backfill_state}" = "ENABLED" ]; then
        echo -e "${GREEN}✓ ${pond}${NC} - Both schedules enabled (15min + daily)"
        enabled_count=$((enabled_count + 2))
    elif [ "${incremental_state}" = "ENABLED" ]; then
        echo -e "${YELLOW}⚠ ${pond}${NC} - Only incremental enabled"
        enabled_count=$((enabled_count + 1))
        disabled_count=$((disabled_count + 1))
    else
        echo -e "${RED}✗ ${pond}${NC} - Schedules disabled or not found"
        disabled_count=$((disabled_count + 2))
    fi
done

echo ""
echo "Summary: ${enabled_count} schedules enabled, ${disabled_count} disabled"

################################################################################
# 5. Overall System Health
################################################################################

echo ""
echo "=========================================="
echo "5. Overall System Health"
echo "=========================================="
echo ""

# Calculate health score
health_checks=0
health_passed=0

# Check if bucket exists
if aws s3 ls "s3://${BUCKET_NAME}" --region "${AWS_REGION}" &>/dev/null; then
    health_checks=$((health_checks + 1))
    health_passed=$((health_passed + 1))
fi

# Check if database exists
if aws glue get-database --name "${DATABASE_NAME}" --region "${AWS_REGION}" &>/dev/null; then
    health_checks=$((health_checks + 1))
    health_passed=$((health_passed + 1))
fi

# Check if at least one lambda exists
if aws lambda get-function --function-name "noaa-ingest-atmospheric-${ENV}" --region "${AWS_REGION}" &>/dev/null; then
    health_checks=$((health_checks + 1))
    health_passed=$((health_passed + 1))
fi

# Check if gold data exists
gold_files=$(aws s3 ls "s3://${BUCKET_NAME}/gold/" --recursive --region "${AWS_REGION}" 2>/dev/null | wc -l | tr -d ' ')
if [ "${gold_files}" -gt 0 ]; then
    health_checks=$((health_checks + 1))
    health_passed=$((health_passed + 1))
fi

# Check if schedules are enabled
if [ ${enabled_count} -gt 6 ]; then
    health_checks=$((health_checks + 1))
    health_passed=$((health_passed + 1))
fi

# Calculate percentage
if [ ${health_checks} -gt 0 ]; then
    health_percentage=$((health_passed * 100 / health_checks))
else
    health_percentage=0
fi

echo "Health Score: ${health_passed}/${health_checks} checks passed (${health_percentage}%)"
echo ""

if [ ${health_percentage} -ge 80 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   System Status: HEALTHY ✓             ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
elif [ ${health_percentage} -ge 50 ]; then
    echo -e "${YELLOW}╔════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   System Status: DEGRADED ⚠            ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   System Status: CRITICAL ✗            ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
fi

################################################################################
# 6. Quick Actions
################################################################################

echo ""
echo "=========================================="
echo "Quick Actions"
echo "=========================================="
echo ""
echo "View logs:"
echo "  aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --follow"
echo ""
echo "Check data in S3:"
echo "  aws s3 ls s3://${BUCKET_NAME}/gold/ --recursive --human-readable | tail -20"
echo ""
echo "Query data with Athena:"
echo "  aws athena start-query-execution --query-string \"SELECT * FROM atmospheric_observations_gold LIMIT 10\" --result-configuration \"OutputLocation=${ATHENA_OUTPUT}\" --query-execution-context \"Database=${DATABASE_NAME}\""
echo ""
echo "Manually trigger ingestion:"
echo "  aws lambda invoke --function-name noaa-ingest-atmospheric-${ENV} --payload '{\"mode\":\"incremental\",\"hours_back\":1}' response.json"
echo ""
echo "View monitoring logs:"
echo "  tail -f deployment/logs/monitor_24h_*.log"
echo ""

echo "=========================================="
echo "Status check complete!"
echo "=========================================="
echo ""
