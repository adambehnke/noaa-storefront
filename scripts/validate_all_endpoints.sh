#!/bin/bash
################################################################################
# NOAA Federated Data Lake - Comprehensive Endpoint Validation Script
#
# Purpose: Test all NOAA endpoints, verify data flow through medallion
#          architecture (Bronze → Silver → Gold), and validate federated API
#
# Usage: ./validate_all_endpoints.sh [--env dev|prod] [--verbose]
#
# Requirements:
#   - AWS CLI configured with appropriate credentials
#   - curl, jq installed
#   - Access to NOAA APIs (no auth required for most)
################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV="${1:-dev}"
VERBOSE="${2:-false}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="validation_report_${TIMESTAMP}.md"

# AWS Configuration
AWS_REGION="us-east-1"
ACCOUNT_ID="899626030376"
BUCKET="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
ATHENA_RESULTS_BUCKET="noaa-athena-results-${ACCOUNT_ID}-${ENV}"
GOLD_DB="noaa_gold_${ENV}"
FEDERATED_API="https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask"

# Test Results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED_TESTS++))
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    ((WARNINGS++))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_TESTS++))
}

print_header() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo ""
}

print_section() {
    echo ""
    echo "--- $1 ---"
    echo ""
}

write_report_header() {
    cat > "$REPORT_FILE" <<EOF
# NOAA Endpoint Validation Report

**Date:** $(date)
**Environment:** $ENV
**Test Run ID:** $TIMESTAMP

---

## Executive Summary

EOF
}

write_report_section() {
    echo "" >> "$REPORT_FILE"
    echo "## $1" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
}

write_report_test() {
    local status=$1
    local test_name=$2
    local details=$3

    if [ "$status" = "PASS" ]; then
        echo "✅ **$test_name**: PASSED" >> "$REPORT_FILE"
    elif [ "$status" = "WARN" ]; then
        echo "⚠️ **$test_name**: WARNING - $details" >> "$REPORT_FILE"
    else
        echo "❌ **$test_name**: FAILED - $details" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"
}

################################################################################
# Test Functions
################################################################################

test_noaa_api_endpoint() {
    local endpoint_name=$1
    local url=$2
    local expected_field=$3

    ((TOTAL_TESTS++))

    log_info "Testing NOAA API: $endpoint_name"

    response=$(curl -s -w "\n%{http_code}" -H "User-Agent: NOAA_Federated_DataLake/1.0" "$url" 2>&1)
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        # Check if response is valid JSON
        if ! echo "$body" | jq empty > /dev/null 2>&1; then
            log_warning "$endpoint_name: Response is not valid JSON"
            write_report_test "WARN" "$endpoint_name" "Invalid JSON response"
            return 1
        fi

        # If expected field is specified, check for it
        if [ ! -z "$expected_field" ]; then
            if echo "$body" | jq -e ".$expected_field" > /dev/null 2>&1; then
                log_success "$endpoint_name: API responding correctly"
                write_report_test "PASS" "$endpoint_name" ""
                return 0
            else
                log_warning "$endpoint_name: Response missing expected field: $expected_field"
                write_report_test "WARN" "$endpoint_name" "Response missing expected field: $expected_field"
                return 1
            fi
        else
            # No expected field, just check valid JSON is enough
            log_success "$endpoint_name: API responding correctly"
            write_report_test "PASS" "$endpoint_name" ""
            return 0
        fi
    else
        log_error "$endpoint_name: HTTP $http_code"
        write_report_test "FAIL" "$endpoint_name" "HTTP status code: $http_code"
        return 1
    fi
}

test_bronze_layer() {
    local pond=$1
    local data_type=$2

    ((TOTAL_TESTS++))

    log_info "Testing Bronze Layer: $pond/$data_type"

    # Check if data exists in S3
    file_count=$(aws s3 ls "s3://${BUCKET}/bronze/${pond}/${data_type}/" --recursive 2>/dev/null | wc -l)

    if [ "$file_count" -gt 0 ]; then
        log_success "Bronze layer has $file_count files for $pond/$data_type"
        write_report_test "PASS" "Bronze: $pond/$data_type" "$file_count files found"

        # Get most recent file
        latest_file=$(aws s3 ls "s3://${BUCKET}/bronze/${pond}/${data_type}/" --recursive | sort | tail -n 1 | awk '{print $4}')

        if [ ! -z "$latest_file" ]; then
            log_info "Latest file: $latest_file"
            echo "  Latest file: \`$latest_file\`" >> "$REPORT_FILE"
        fi

        return 0
    else
        log_warning "No files found in Bronze layer for $pond/$data_type"
        write_report_test "WARN" "Bronze: $pond/$data_type" "No files found"
        return 1
    fi
}

test_gold_layer() {
    local table_name=$1
    local test_query=$2

    ((TOTAL_TESTS++))

    log_info "Testing Gold Layer: $table_name"

    # Execute Athena query
    query_id=$(aws athena start-query-execution \
        --query-string "$test_query" \
        --query-execution-context "Database=${GOLD_DB}" \
        --result-configuration "OutputLocation=s3://${ATHENA_RESULTS_BUCKET}/" \
        --region "$AWS_REGION" \
        --output text \
        --query 'QueryExecutionId' 2>&1)

    if [ $? -ne 0 ]; then
        log_error "Failed to start Athena query for $table_name"
        write_report_test "FAIL" "Gold: $table_name" "Query execution failed"
        return 1
    fi

    # Wait for query to complete
    log_info "Waiting for Athena query to complete..."
    sleep 5

    max_attempts=12
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        status=$(aws athena get-query-execution \
            --query-execution-id "$query_id" \
            --region "$AWS_REGION" \
            --output text \
            --query 'QueryExecution.Status.State' 2>&1)

        if [ "$status" = "SUCCEEDED" ]; then
            # Get results
            results=$(aws athena get-query-results \
                --query-execution-id "$query_id" \
                --region "$AWS_REGION" \
                --output json 2>&1)

            row_count=$(echo "$results" | jq '.ResultSet.Rows | length')

            if [ "$row_count" -gt 1 ]; then
                log_success "Gold layer query successful: $table_name ($((row_count - 1)) rows)"
                write_report_test "PASS" "Gold: $table_name" "$((row_count - 1)) rows returned"
                return 0
            else
                log_warning "Gold layer query returned no data: $table_name"
                write_report_test "WARN" "Gold: $table_name" "No data rows returned"
                return 1
            fi
        elif [ "$status" = "FAILED" ] || [ "$status" = "CANCELLED" ]; then
            log_error "Athena query failed for $table_name: $status"
            write_report_test "FAIL" "Gold: $table_name" "Query status: $status"
            return 1
        fi

        sleep 5
        ((attempt++))
    done

    log_error "Athena query timeout for $table_name"
    write_report_test "FAIL" "Gold: $table_name" "Query timeout"
    return 1
}

test_federated_api() {
    local test_name=$1
    local question=$2
    local expected_pond=$3

    ((TOTAL_TESTS++))

    log_info "Testing Federated API: $test_name"

    response=$(curl -s -X POST "$FEDERATED_API" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"$question\"}" 2>&1)

    if [ $? -ne 0 ]; then
        log_error "API request failed for: $test_name"
        write_report_test "FAIL" "API: $test_name" "Request failed"
        return 1
    fi

    # Check if response contains answer
    if echo "$response" | jq -e '.answer' > /dev/null 2>&1; then
        answer=$(echo "$response" | jq -r '.answer' | head -c 100)
        log_success "API returned answer for: $test_name"
        write_report_test "PASS" "API: $test_name" "Response received"

        # Check if expected pond was queried
        if [ ! -z "$expected_pond" ]; then
            if echo "$response" | jq -e ".data_sources[] | select(.pond == \"$expected_pond\")" > /dev/null 2>&1; then
                log_success "Response included data from $expected_pond pond"
                echo "  Data source: \`$expected_pond\` pond" >> "$REPORT_FILE"
            else
                log_warning "Response did not include data from $expected_pond pond"
            fi
        fi

        if [ "$VERBOSE" = "--verbose" ]; then
            echo "Sample response: ${answer}..."
        fi

        return 0
    else
        log_error "API returned invalid response for: $test_name"
        write_report_test "FAIL" "API: $test_name" "Invalid response structure"
        return 1
    fi
}

################################################################################
# Main Test Execution
################################################################################

main() {
    print_header "NOAA Federated Data Lake - Endpoint Validation"

    log_info "Environment: $ENV"
    log_info "Bucket: $BUCKET"
    log_info "Database: $GOLD_DB"
    log_info "API: $FEDERATED_API"

    write_report_header

    # =========================================================================
    # OCEANIC POND TESTS
    # =========================================================================

    print_section "Testing OCEANIC POND"
    write_report_section "Oceanic Pond (CO-OPS)"

    # Test 1: Water Temperature API
    test_noaa_api_endpoint \
        "Water Temperature API" \
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=8723214&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake" \
        "data"

    # Test 2: Water Levels API
    test_noaa_api_endpoint \
        "Water Levels API" \
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&station=8723214&date=latest&datum=MLLW&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake" \
        "data"

    # Test 3: Bronze Layer - Water Temperature
    test_bronze_layer "oceanic" "water_temperature"

    # Test 4: Bronze Layer - Water Level
    test_bronze_layer "oceanic" "water_level"

    # Test 5: Gold Layer - Oceanic Aggregated
    test_gold_layer \
        "oceanic_aggregated" \
        "SELECT station_id, station_name, avg_water_temp, date FROM ${GOLD_DB}.oceanic_aggregated WHERE station_id = '8723214' ORDER BY date DESC LIMIT 5"

    # Test 6: Federated API - Water Temperature Query
    test_federated_api \
        "Water Temperature Query" \
        "What is the ocean temperature in Florida?" \
        "oceanic"

    # =========================================================================
    # ATMOSPHERIC POND TESTS
    # =========================================================================

    print_section "Testing ATMOSPHERIC POND"
    write_report_section "Atmospheric Pond (NWS)"

    # Test 7: Active Alerts API
    test_noaa_api_endpoint \
        "Active Weather Alerts API" \
        "https://api.weather.gov/alerts/active?limit=1" \
        "features"

    # Test 8: NWS Points API
    test_noaa_api_endpoint \
        "NWS Points API (NYC)" \
        "https://api.weather.gov/points/40.7128,-74.0060" \
        "properties"

    # Test 9: Federated API - Weather Query
    test_federated_api \
        "Current Weather Query" \
        "What is the current weather in New York City?" \
        "atmospheric"

    # Test 10: Federated API - Alerts Query
    test_federated_api \
        "Weather Alerts Query" \
        "Are there any severe weather warnings in California?" \
        "atmospheric"

    # =========================================================================
    # MULTI-POND FEDERATED TESTS
    # =========================================================================

    print_section "Testing MULTI-POND FEDERATION"
    write_report_section "Multi-Pond Federated Queries"

    # Test 11: Cross-Pond Query
    test_federated_api \
        "Cross-Pond Query" \
        "What is the weather in Miami and what is the ocean temperature in Florida?" \
        ""

    # Test 12: Multi-Location Query
    test_federated_api \
        "Multi-Location Query" \
        "What are the water levels along the California coast?" \
        "oceanic"

    # =========================================================================
    # BUOY POND TESTS (Expected to fail - not yet implemented)
    # =========================================================================

    print_section "Testing BUOY POND (Expected Warnings)"
    write_report_section "Buoy Pond (NDBC) - Not Yet Implemented"

    # Test 13: NDBC API (direct test only)
    test_noaa_api_endpoint \
        "NDBC Latest Observations" \
        "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt" \
        "" || log_warning "NDBC endpoint returns text format (expected)"

    # =========================================================================
    # SYSTEM HEALTH CHECKS
    # =========================================================================

    print_section "Testing SYSTEM HEALTH"
    write_report_section "System Health & Infrastructure"

    # Test 14: S3 Bucket Access
    ((TOTAL_TESTS++))
    if aws s3 ls "s3://${BUCKET}/" > /dev/null 2>&1; then
        log_success "S3 bucket accessible"
        write_report_test "PASS" "S3 Bucket Access" ""
    else
        log_error "Cannot access S3 bucket"
        write_report_test "FAIL" "S3 Bucket Access" "Access denied"
    fi

    # Test 15: Athena Database
    ((TOTAL_TESTS++))
    tables=$(aws athena start-query-execution \
        --query-string "SHOW TABLES IN ${GOLD_DB}" \
        --query-execution-context "Database=${GOLD_DB}" \
        --result-configuration "OutputLocation=s3://${ATHENA_RESULTS_BUCKET}/" \
        --region "$AWS_REGION" 2>&1)

    if [ $? -eq 0 ]; then
        log_success "Athena database accessible"
        write_report_test "PASS" "Athena Database" ""
    else
        log_error "Cannot access Athena database"
        write_report_test "FAIL" "Athena Database" "Access denied"
    fi

    # Test 16: Lambda Function
    ((TOTAL_TESTS++))
    lambda_status=$(aws lambda get-function \
        --function-name "noaa-enhanced-handler-${ENV}" \
        --region "$AWS_REGION" 2>&1)

    if [ $? -eq 0 ]; then
        log_success "Lambda function exists and accessible"
        write_report_test "PASS" "Lambda Function" ""
    else
        log_error "Cannot access Lambda function"
        write_report_test "FAIL" "Lambda Function" "Not found or access denied"
    fi

    # =========================================================================
    # GENERATE FINAL REPORT
    # =========================================================================

    print_header "Test Summary"

    echo "Total Tests:  $TOTAL_TESTS"
    echo "Passed:       ${GREEN}$PASSED_TESTS${NC}"
    echo "Warnings:     ${YELLOW}$WARNINGS${NC}"
    echo "Failed:       ${RED}$FAILED_TESTS${NC}"

    # Calculate success rate
    if [ $TOTAL_TESTS -gt 0 ]; then
        success_rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED_TESTS / $TOTAL_TESTS) * 100}")
        echo "Success Rate: ${success_rate}%"
    fi

    # Write summary to report
    cat >> "$REPORT_FILE" <<EOF

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tests | $TOTAL_TESTS |
| Passed | $PASSED_TESTS |
| Warnings | $WARNINGS |
| Failed | $FAILED_TESTS |
| Success Rate | ${success_rate}% |

---

## Recommendations

### Immediate Actions Required
EOF

    if [ $FAILED_TESTS -gt 0 ]; then
        echo "- Investigate and resolve $FAILED_TESTS failed test(s)" >> "$REPORT_FILE"
    fi

    if [ $WARNINGS -gt 0 ]; then
        echo "- Review $WARNINGS warning(s) for potential improvements" >> "$REPORT_FILE"
    fi

    cat >> "$REPORT_FILE" <<EOF

### Next Steps for Implementation

1. **Complete Buoy Pond Ingestion**
   - Implement NDBC text file parser
   - Create Bronze/Silver/Gold pipeline for buoy data
   - Estimated effort: 3-5 days

2. **Add Climate Data Online (CDO)**
   - Implement CDO API integration (token already configured)
   - Historical climate data ingestion
   - Estimated effort: 5-7 days

3. **Implement Additional CO-OPS Products**
   - Tide predictions
   - Currents
   - Salinity
   - Estimated effort: 2-3 days each

4. **Enhance Monitoring**
   - CloudWatch dashboards for data freshness
   - SNS alerts for ingestion failures
   - Automated daily validation runs

---

**Generated:** $(date)
**Report File:** $REPORT_FILE
EOF

    echo ""
    log_info "Detailed report saved to: $REPORT_FILE"
    echo ""

    # Exit with appropriate code
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@"
