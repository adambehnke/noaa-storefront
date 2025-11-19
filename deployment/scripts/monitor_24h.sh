#!/bin/bash

################################################################################
# NOAA 24-Hour Continuous Monitoring Script
# Checks ingestion status every 15 minutes for 24 hours
# Diagnoses query issues and verifies data flow
################################################################################

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
BUCKET_NAME="noaa-data-lake-${ENV}"
DATABASE_NAME="noaa_federated_${ENV}"
ATHENA_OUTPUT="s3://${BUCKET_NAME}/athena-results/"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Monitoring duration
MONITOR_HOURS=24
CHECK_INTERVAL_MINUTES=15
TOTAL_CHECKS=$((MONITOR_HOURS * 60 / CHECK_INTERVAL_MINUTES))

# Log file
LOG_DIR="deployment/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/monitor_24h_$(date +%Y%m%d_%H%M%S).log"

# Data ponds to monitor
PONDS=("atmospheric" "oceanic" "buoy" "climate" "spatial" "terrestrial")

################################################################################
# Logging Functions
################################################################################

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    log "INFO" "${BLUE}$@${NC}"
}

log_success() {
    log "SUCCESS" "${GREEN}$@${NC}"
}

log_warning() {
    log "WARNING" "${YELLOW}$@${NC}"
}

log_error() {
    log "ERROR" "${RED}$@${NC}"
}

################################################################################
# Check Functions
################################################################################

check_lambda_status() {
    local pond=$1
    local lambda_name="noaa-ingest-${pond}-${ENV}"

    log_info "Checking Lambda: ${lambda_name}"

    # Check if lambda exists
    if ! aws lambda get-function --function-name "${lambda_name}" --region "${AWS_REGION}" &>/dev/null; then
        log_error "Lambda ${lambda_name} not found!"
        return 1
    fi

    # Get last execution status from CloudWatch
    local log_group="/aws/lambda/${lambda_name}"
    local recent_logs=$(aws logs filter-log-events \
        --log-group-name "${log_group}" \
        --start-time $(($(date +%s) * 1000 - 3600000)) \
        --filter-pattern "Ingestion complete" \
        --region "${AWS_REGION}" \
        --query 'events[0].message' \
        --output text 2>/dev/null)

    if [ -n "${recent_logs}" ] && [ "${recent_logs}" != "None" ]; then
        log_success "Lambda ${lambda_name}: Recent execution found"
        echo "  ${recent_logs}" | tee -a "${LOG_FILE}"
        return 0
    else
        log_warning "Lambda ${lambda_name}: No recent executions found"
        return 1
    fi
}

check_s3_data() {
    local pond=$1
    local layer=$2

    log_info "Checking S3 data: ${pond}/${layer}"

    # Check for recent files (last hour)
    local recent_files=$(aws s3 ls "s3://${BUCKET_NAME}/${layer}/${pond}/" \
        --recursive \
        --region "${AWS_REGION}" \
        | awk '{print $1" "$2}' \
        | sort -r \
        | head -1)

    if [ -n "${recent_files}" ]; then
        log_success "S3 ${layer}/${pond}: Data found (latest: ${recent_files})"

        # Count files
        local file_count=$(aws s3 ls "s3://${BUCKET_NAME}/${layer}/${pond}/" \
            --recursive \
            --region "${AWS_REGION}" \
            | wc -l)
        echo "  Total files: ${file_count}" | tee -a "${LOG_FILE}"

        # Show size
        local total_size=$(aws s3 ls "s3://${BUCKET_NAME}/${layer}/${pond}/" \
            --recursive \
            --human-readable \
            --summarize \
            --region "${AWS_REGION}" \
            | grep "Total Size" \
            | awk '{print $3" "$4}')
        echo "  Total size: ${total_size}" | tee -a "${LOG_FILE}"

        return 0
    else
        log_error "S3 ${layer}/${pond}: No data found!"
        return 1
    fi
}

check_glue_table() {
    local pond=$1
    local layer=$2
    local table_name="${pond}_${layer}"

    log_info "Checking Glue table: ${table_name}"

    if aws glue get-table \
        --database-name "${DATABASE_NAME}" \
        --name "${table_name}" \
        --region "${AWS_REGION}" &>/dev/null; then
        log_success "Glue table ${table_name}: Exists"
        return 0
    else
        log_error "Glue table ${table_name}: Not found!"
        return 1
    fi
}

run_athena_query() {
    local query=$1
    local description=$2

    log_info "Running Athena query: ${description}"

    # Start query execution
    local query_id=$(aws athena start-query-execution \
        --query-string "${query}" \
        --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
        --query-execution-context "Database=${DATABASE_NAME}" \
        --region "${AWS_REGION}" \
        --query 'QueryExecutionId' \
        --output text 2>&1)

    if [ $? -ne 0 ] || [ -z "${query_id}" ]; then
        log_error "Failed to start query: ${query_id}"
        return 1
    fi

    # Wait for query to complete (max 60 seconds)
    for i in {1..60}; do
        local status=$(aws athena get-query-execution \
            --query-execution-id "${query_id}" \
            --region "${AWS_REGION}" \
            --query 'QueryExecution.Status.State' \
            --output text 2>&1)

        if [ "${status}" = "SUCCEEDED" ]; then
            # Get results
            local results=$(aws athena get-query-results \
                --query-execution-id "${query_id}" \
                --region "${AWS_REGION}" \
                --query 'ResultSet.Rows[1:].Data[0].VarCharValue' \
                --output text 2>&1)

            if [ -n "${results}" ] && [ "${results}" != "None" ] && [ "${results}" != "" ]; then
                log_success "Query succeeded: ${results}"
                return 0
            else
                log_warning "Query succeeded but returned no data"
                return 1
            fi
        elif [ "${status}" = "FAILED" ] || [ "${status}" = "CANCELLED" ]; then
            local error=$(aws athena get-query-execution \
                --query-execution-id "${query_id}" \
                --region "${AWS_REGION}" \
                --query 'QueryExecution.Status.StateChangeReason' \
                --output text 2>&1)
            log_error "Query failed: ${error}"
            return 1
        fi

        sleep 1
    done

    log_warning "Query timeout"
    return 1
}

check_athena_queries() {
    local pond=$1

    log_info "Testing Athena queries for ${pond} pond..."

    # First, repair partitions
    log_info "Repairing partitions for ${pond}_gold..."
    aws athena start-query-execution \
        --query-string "MSCK REPAIR TABLE ${pond}_gold" \
        --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
        --query-execution-context "Database=${DATABASE_NAME}" \
        --region "${AWS_REGION}" &>/dev/null

    sleep 5

    # Test query
    local query="SELECT COUNT(*) as record_count FROM ${pond}_gold"
    run_athena_query "${query}" "${pond}_gold record count"
}

check_eventbridge_schedules() {
    local pond=$1
    local lambda_name="noaa-ingest-${pond}-${ENV}"

    log_info "Checking EventBridge schedules for ${pond}"

    # Check incremental schedule
    local incremental_rule="${lambda_name}-incremental"
    local incremental_state=$(aws events describe-rule \
        --name "${incremental_rule}" \
        --region "${AWS_REGION}" \
        --query 'State' \
        --output text 2>/dev/null)

    if [ "${incremental_state}" = "ENABLED" ]; then
        log_success "Incremental schedule: ENABLED"
    else
        log_error "Incremental schedule: ${incremental_state}"
    fi

    # Check backfill schedule
    local backfill_rule="${lambda_name}-backfill"
    local backfill_state=$(aws events describe-rule \
        --name "${backfill_rule}" \
        --region "${AWS_REGION}" \
        --query 'State' \
        --output text 2>/dev/null)

    if [ "${backfill_state}" = "ENABLED" ]; then
        log_success "Backfill schedule: ENABLED"
    else
        log_error "Backfill schedule: ${backfill_state}"
    fi
}

manual_trigger_lambda() {
    local pond=$1
    local lambda_name="noaa-ingest-${pond}-${ENV}"

    log_info "Manually triggering ${lambda_name}..."

    aws lambda invoke \
        --function-name "${lambda_name}" \
        --invocation-type Event \
        --payload '{"mode":"incremental","hours_back":1}' \
        --region "${AWS_REGION}" \
        /tmp/lambda_response.json &>/dev/null

    if [ $? -eq 0 ]; then
        log_success "Lambda ${lambda_name} triggered successfully"
        return 0
    else
        log_error "Failed to trigger ${lambda_name}"
        return 1
    fi
}

################################################################################
# Main Check Function
################################################################################

run_comprehensive_check() {
    local check_number=$1

    echo ""
    echo "=========================================="
    log_info "CHECK #${check_number} of ${TOTAL_CHECKS}"
    log_info "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""

    local total_checks=0
    local passed_checks=0

    for pond in "${PONDS[@]}"; do
        echo ""
        log_info "===== CHECKING ${pond} POND ====="
        echo ""

        # Check Lambda
        ((total_checks++))
        if check_lambda_status "${pond}"; then
            ((passed_checks++))
        fi

        # Check S3 Gold layer (most important for queries)
        ((total_checks++))
        if check_s3_data "${pond}" "gold"; then
            ((passed_checks++))
        fi

        # Check Glue table
        ((total_checks++))
        if check_glue_table "${pond}" "gold"; then
            ((passed_checks++))
        fi

        # Check EventBridge schedules
        ((total_checks++))
        if check_eventbridge_schedules "${pond}"; then
            ((passed_checks++))
        fi

        # Try Athena query
        ((total_checks++))
        if check_athena_queries "${pond}"; then
            ((passed_checks++))
        else
            # If query fails, try to manually trigger ingestion
            log_warning "Queries failing for ${pond}, attempting manual trigger..."
            manual_trigger_lambda "${pond}"
        fi

        echo ""
    done

    # Summary
    echo ""
    echo "=========================================="
    log_info "CHECK #${check_number} SUMMARY"
    echo "=========================================="
    log_info "Passed: ${passed_checks}/${total_checks} checks"
    local pass_rate=$((passed_checks * 100 / total_checks))

    if [ ${pass_rate} -ge 80 ]; then
        log_success "System Health: GOOD (${pass_rate}%)"
    elif [ ${pass_rate} -ge 50 ]; then
        log_warning "System Health: DEGRADED (${pass_rate}%)"
    else
        log_error "System Health: CRITICAL (${pass_rate}%)"
    fi

    echo ""
    log_info "Next check in ${CHECK_INTERVAL_MINUTES} minutes..."
    echo "=========================================="
    echo ""
}

################################################################################
# Diagnostic Function (Run Once at Start)
################################################################################

run_initial_diagnostics() {
    echo ""
    echo "=========================================="
    log_info "INITIAL DIAGNOSTICS"
    echo "=========================================="
    echo ""

    # Check AWS credentials
    log_info "Checking AWS credentials..."
    if aws sts get-caller-identity --region "${AWS_REGION}" &>/dev/null; then
        local account=$(aws sts get-caller-identity --query 'Account' --output text)
        log_success "AWS credentials valid (Account: ${account})"
    else
        log_error "AWS credentials invalid!"
        exit 1
    fi

    # Check S3 bucket
    log_info "Checking S3 bucket..."
    if aws s3 ls "s3://${BUCKET_NAME}" --region "${AWS_REGION}" &>/dev/null; then
        log_success "S3 bucket accessible: ${BUCKET_NAME}"
    else
        log_error "S3 bucket not accessible: ${BUCKET_NAME}"
        exit 1
    fi

    # Check Glue database
    log_info "Checking Glue database..."
    if aws glue get-database --name "${DATABASE_NAME}" --region "${AWS_REGION}" &>/dev/null; then
        log_success "Glue database exists: ${DATABASE_NAME}"
    else
        log_error "Glue database not found: ${DATABASE_NAME}"
        exit 1
    fi

    # Check all Lambda functions
    log_info "Checking Lambda functions..."
    for pond in "${PONDS[@]}"; do
        local lambda_name="noaa-ingest-${pond}-${ENV}"
        if aws lambda get-function --function-name "${lambda_name}" --region "${AWS_REGION}" &>/dev/null; then
            log_success "Lambda exists: ${lambda_name}"
        else
            log_error "Lambda not found: ${lambda_name}"
        fi
    done

    echo ""
    log_success "Initial diagnostics complete!"
    echo ""
}

################################################################################
# Main Monitoring Loop
################################################################################

main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  NOAA 24-Hour Continuous Monitoring System              ║"
    echo "║  Checking every ${CHECK_INTERVAL_MINUTES} minutes for ${MONITOR_HOURS} hours                    ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

    log_info "Monitoring started at $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "Log file: ${LOG_FILE}"
    log_info "Total checks: ${TOTAL_CHECKS}"
    log_info "Check interval: ${CHECK_INTERVAL_MINUTES} minutes"
    log_info "Duration: ${MONITOR_HOURS} hours"
    echo ""

    # Run initial diagnostics
    run_initial_diagnostics

    # Main monitoring loop
    for check_num in $(seq 1 ${TOTAL_CHECKS}); do
        run_comprehensive_check ${check_num}

        # Sleep unless it's the last check
        if [ ${check_num} -lt ${TOTAL_CHECKS} ]; then
            sleep $((CHECK_INTERVAL_MINUTES * 60))
        fi
    done

    echo ""
    echo "=========================================="
    log_success "24-HOUR MONITORING COMPLETE"
    echo "=========================================="
    log_info "Completed at $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "Total checks performed: ${TOTAL_CHECKS}"
    log_info "Log file: ${LOG_FILE}"
    echo ""

    # Generate summary report
    echo ""
    log_info "Generating summary report..."
    echo ""
    echo "Summary Report" | tee -a "${LOG_FILE}"
    echo "==============" | tee -a "${LOG_FILE}"
    grep -c "SUCCESS" "${LOG_FILE}" | xargs -I {} echo "Total successes: {}" | tee -a "${LOG_FILE}"
    grep -c "ERROR" "${LOG_FILE}" | xargs -I {} echo "Total errors: {}" | tee -a "${LOG_FILE}"
    grep -c "WARNING" "${LOG_FILE}" | xargs -I {} echo "Total warnings: {}" | tee -a "${LOG_FILE}"
    echo ""
}

# Trap Ctrl+C and cleanup
trap 'echo ""; log_warning "Monitoring interrupted by user"; exit 130' INT

# Run main function
main "$@"
