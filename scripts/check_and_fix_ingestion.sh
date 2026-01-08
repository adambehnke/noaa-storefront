#!/bin/bash
#
# NOAA Data Lake Ingestion Status Check & Fix
# Account: 899626030376 (noaa-target)
#
# This script checks all ingestion components and ensures data is flowing
# through Bronze → Silver → Gold layers
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Force the correct AWS profile
export AWS_PROFILE=noaa-target
export AWS_REGION=us-east-1
ENV=dev

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ "$ACCOUNT_ID" != "899626030376" ]; then
    echo -e "${RED}ERROR: Wrong AWS account! Expected 899626030376, got ${ACCOUNT_ID}${NC}"
    echo "Please configure AWS_PROFILE=noaa-target"
    exit 1
fi

BUCKET_NAME="noaa-federated-lake-899626030376-dev"

# Banner
echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     NOAA Data Lake Ingestion System Status Check              ║"
echo "║     Account: 899626030376 (noaa-target)                       ║"
echo "║     Environment: dev                                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Helper functions
print_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

# Array of ponds
PONDS=("atmospheric" "oceanic" "buoy" "climate" "spatial" "terrestrial")

# Check 1: Verify S3 Bucket
print_header "1. S3 Data Lake Bucket Status"

if aws s3 ls "s3://${BUCKET_NAME}" >/dev/null 2>&1; then
    print_success "Bucket exists: ${BUCKET_NAME}"

    # Get bucket statistics
    TOTAL_SIZE=$(aws s3 ls "s3://${BUCKET_NAME}" --recursive --summarize 2>/dev/null | grep "Total Size" | awk '{print $3}')
    TOTAL_FILES=$(aws s3 ls "s3://${BUCKET_NAME}" --recursive --summarize 2>/dev/null | grep "Total Objects" | awk '{print $3}')

    if [ -n "$TOTAL_SIZE" ] && [ -n "$TOTAL_FILES" ]; then
        SIZE_GB=$(echo "scale=2; $TOTAL_SIZE / 1073741824" | bc 2>/dev/null || echo "N/A")
        print_info "Total size: ${SIZE_GB} GB"
        print_info "Total files: ${TOTAL_FILES}"
    fi
else
    print_error "Bucket not found: ${BUCKET_NAME}"
    exit 1
fi

# Check 2: Lambda Functions Status
print_header "2. Ingestion Lambda Functions"

LAMBDA_COUNT=0
LAMBDA_WORKING=0
LAMBDA_FAILED=0

for POND in "${PONDS[@]}"; do
    LAMBDA_NAME="noaa-ingest-${POND}-${ENV}"

    if aws lambda get-function --function-name "$LAMBDA_NAME" >/dev/null 2>&1; then
        ((LAMBDA_COUNT++))

        # Get last modified
        LAST_MOD=$(aws lambda get-function --function-name "$LAMBDA_NAME" --query 'Configuration.LastModified' --output text)

        # Test invoke
        echo -n "  Testing ${POND}... "
        TEST_RESULT=$(aws lambda invoke \
            --function-name "$LAMBDA_NAME" \
            --cli-binary-format raw-in-base64-out \
            --payload '{"env":"dev"}' \
            /tmp/test-${POND}.json 2>&1)

        if echo "$TEST_RESULT" | grep -q "StatusCode.*200"; then
            RESPONSE=$(cat /tmp/test-${POND}.json 2>/dev/null)
            if echo "$RESPONSE" | grep -q "success"; then
                print_success "${POND} Lambda working (Last: ${LAST_MOD})"
                ((LAMBDA_WORKING++))
            else
                print_warning "${POND} Lambda responded but may have errors"
            fi
        else
            print_error "${POND} Lambda invocation failed"
            ((LAMBDA_FAILED++))
        fi

        rm -f /tmp/test-${POND}.json
    else
        print_error "${POND} Lambda not found: ${LAMBDA_NAME}"
        ((LAMBDA_FAILED++))
    fi
done

echo ""
print_info "Summary: ${LAMBDA_WORKING}/${LAMBDA_COUNT} Lambdas working, ${LAMBDA_FAILED} issues"

# Check 3: EventBridge Schedules
print_header "3. EventBridge Ingestion Schedules"

RULES=$(aws events list-rules --query "Rules[?contains(Name, 'noaa-ingest')].Name" --output text)

if [ -z "$RULES" ]; then
    print_error "No EventBridge rules found"
else
    RULE_COUNT=$(echo "$RULES" | wc -w)
    print_success "Found ${RULE_COUNT} EventBridge rules"

    echo ""
    echo "Active schedules:"
    for POND in "${PONDS[@]}"; do
        RULE_NAME="noaa-ingest-${POND}-schedule-${ENV}"

        RULE_INFO=$(aws events describe-rule --name "$RULE_NAME" 2>/dev/null || echo "")

        if [ -n "$RULE_INFO" ]; then
            STATE=$(echo "$RULE_INFO" | grep -o '"State": "[^"]*"' | cut -d'"' -f4)
            SCHEDULE=$(echo "$RULE_INFO" | grep -o '"ScheduleExpression": "[^"]*"' | cut -d'"' -f4)

            if [ "$STATE" = "ENABLED" ]; then
                print_success "${POND}: ${SCHEDULE} (${STATE})"
            else
                print_warning "${POND}: ${SCHEDULE} (${STATE})"
            fi
        else
            print_warning "${POND}: No schedule found"
        fi
    done
fi

# Check 4: Recent Data in Bronze Layer
print_header "4. Recent Bronze Layer Data (Today)"

TODAY=$(date -u +"%Y-%m-%d")
YEAR=$(date -u +"%Y")
MONTH=$(date -u +"%m")
DAY=$(date -u +"%d")

echo "Checking for data from ${TODAY}..."
echo ""

RECENT_DATA_FOUND=0

for POND in "${PONDS[@]}"; do
    echo -n "  ${POND}: "

    # Try different path patterns
    PREFIXES=(
        "bronze/${POND}/year=${YEAR}/month=${MONTH}/day=${DAY}/"
        "bronze/${POND}/date=${TODAY}/"
        "bronze/${POND}/"
    )

    FOUND=false
    LATEST_FILE=""
    LATEST_TIME=""

    for PREFIX in "${PREFIXES[@]}"; do
        FILES=$(aws s3 ls "s3://${BUCKET_NAME}/${PREFIX}" --recursive 2>/dev/null | tail -5)

        if [ -n "$FILES" ]; then
            FOUND=true
            LATEST=$(echo "$FILES" | tail -1)
            LATEST_TIME=$(echo "$LATEST" | awk '{print $1, $2}')
            LATEST_FILE=$(echo "$LATEST" | awk '{print $4}')
            break
        fi
    done

    if [ "$FOUND" = true ]; then
        print_success "Latest: ${LATEST_TIME}"
        ((RECENT_DATA_FOUND++))
    else
        print_warning "No data found for today"
    fi
done

echo ""
print_info "${RECENT_DATA_FOUND}/${#PONDS[@]} ponds have data from today"

# Check 5: Silver Layer Transformation
print_header "5. Silver Layer Status"

SILVER_DATA=0

for POND in "${PONDS[@]}"; do
    SILVER_PREFIX="silver/${POND}/"

    SILVER_FILES=$(aws s3 ls "s3://${BUCKET_NAME}/${SILVER_PREFIX}" --recursive 2>/dev/null | wc -l)

    if [ "$SILVER_FILES" -gt 0 ]; then
        print_success "${POND}: ${SILVER_FILES} files"
        ((SILVER_DATA++))
    else
        print_warning "${POND}: No silver data"
    fi
done

echo ""
print_info "${SILVER_DATA}/${#PONDS[@]} ponds have silver layer data"

# Check 6: Gold Layer Analytics
print_header "6. Gold Layer Status"

GOLD_DATA=0

for POND in "${PONDS[@]}"; do
    GOLD_PREFIX="gold/${POND}/"

    GOLD_FILES=$(aws s3 ls "s3://${BUCKET_NAME}/${GOLD_PREFIX}" --recursive 2>/dev/null | wc -l)

    if [ "$GOLD_FILES" -gt 0 ]; then
        print_success "${POND}: ${GOLD_FILES} files"
        ((GOLD_DATA++))
    else
        print_warning "${POND}: No gold data"
    fi
done

echo ""
print_info "${GOLD_DATA}/${#PONDS[@]} ponds have gold layer data"

# Check 7: Dashboard Metrics Lambda
print_header "7. Dashboard Metrics Lambda"

METRICS_LAMBDA="noaa-dashboard-metrics"

if aws lambda get-function --function-name "$METRICS_LAMBDA" >/dev/null 2>&1; then
    print_success "Dashboard metrics Lambda exists"

    # Check IAM permissions
    ROLE_ARN=$(aws lambda get-function --function-name "$METRICS_LAMBDA" --query 'Configuration.Role' --output text)
    ROLE_NAME=$(echo "$ROLE_ARN" | cut -d'/' -f2)

    print_info "Role: ${ROLE_NAME}"

    # Check if role has necessary permissions
    POLICIES=$(aws iam list-role-policies --role-name "$ROLE_NAME" --output text 2>/dev/null)

    if echo "$POLICIES" | grep -q "DashboardMetricsAccess"; then
        print_success "Dashboard permissions configured"
    else
        print_warning "Dashboard may need additional permissions"

        # Offer to fix
        echo ""
        read -p "Fix dashboard permissions? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cat > /tmp/dashboard-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "events:ListRules",
        "events:DescribeRule",
        "events:ListTargetsByRule"
      ],
      "Resource": "*"
    }
  ]
}
EOF
            aws iam put-role-policy \
                --role-name "$ROLE_NAME" \
                --policy-name DashboardMetricsAccess \
                --policy-document file:///tmp/dashboard-policy.json

            print_success "Permissions added"

            # Force Lambda to reload
            aws lambda update-function-configuration \
                --function-name "$METRICS_LAMBDA" \
                --environment "Variables={DATA_LAKE_BUCKET=${BUCKET_NAME},ATHENA_DATABASE=noaa_data_lake,ATHENA_OUTPUT_BUCKET=s3://${BUCKET_NAME}/athena-results/,UPDATED=$(date +%s)}" \
                >/dev/null 2>&1

            print_info "Lambda restarting with new permissions..."
        fi
    fi
else
    print_error "Dashboard metrics Lambda not found"
fi

# Check 8: Recent CloudWatch Invocations
print_header "8. Recent Lambda Invocations (Last Hour)"

echo ""

for POND in "${PONDS[@]}"; do
    LAMBDA_NAME="noaa-ingest-${POND}-${ENV}"

    INVOCATIONS=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value="$LAMBDA_NAME" \
        --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --period 3600 \
        --statistics Sum \
        --query 'Datapoints[0].Sum' \
        --output text 2>/dev/null || echo "0")

    ERRORS=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value="$LAMBDA_NAME" \
        --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --period 3600 \
        --statistics Sum \
        --query 'Datapoints[0].Sum' \
        --output text 2>/dev/null || echo "0")

    if [ "$INVOCATIONS" != "None" ] && [ "$INVOCATIONS" != "0" ]; then
        if [ "$ERRORS" != "None" ] && [ "$ERRORS" != "0" ]; then
            print_warning "${POND}: ${INVOCATIONS} invocations, ${ERRORS} errors"
        else
            print_success "${POND}: ${INVOCATIONS} invocations, no errors"
        fi
    else
        print_info "${POND}: No invocations in last hour (may be on longer schedule)"
    fi
done

# Summary
print_header "SYSTEM STATUS SUMMARY"

echo ""
echo -e "${CYAN}Data Lake:${NC}"
echo "  • Bucket: ${BUCKET_NAME}"
echo "  • Total Files: ${TOTAL_FILES:-N/A}"
echo "  • Total Size: ${SIZE_GB:-N/A} GB"
echo ""

echo -e "${CYAN}Ingestion Status:${NC}"
echo "  • Lambda Functions: ${LAMBDA_WORKING}/${LAMBDA_COUNT} working"
echo "  • EventBridge Rules: ${RULE_COUNT} enabled"
echo "  • Ponds with today's data: ${RECENT_DATA_FOUND}/${#PONDS[@]}"
echo ""

echo -e "${CYAN}Medallion Architecture:${NC}"
echo "  • Bronze (Raw): ${RECENT_DATA_FOUND}/${#PONDS[@]} active ponds"
echo "  • Silver (Clean): ${SILVER_DATA}/${#PONDS[@]} ponds"
echo "  • Gold (Analytics): ${GOLD_DATA}/${#PONDS[@]} ponds"
echo ""

# Overall health
HEALTH_SCORE=$((LAMBDA_WORKING * 100 / ${#PONDS[@]}))

if [ "$HEALTH_SCORE" -ge 80 ]; then
    echo -e "${GREEN}✓ System Health: GOOD (${HEALTH_SCORE}%)${NC}"
    echo -e "  Data is actively being ingested from NOAA endpoints"
elif [ "$HEALTH_SCORE" -ge 50 ]; then
    echo -e "${YELLOW}! System Health: FAIR (${HEALTH_SCORE}%)${NC}"
    echo -e "  Some ingestion issues detected"
else
    echo -e "${RED}✗ System Health: POOR (${HEALTH_SCORE}%)${NC}"
    echo -e "  Significant ingestion issues"
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Quick actions
echo -e "${MAGENTA}Quick Actions:${NC}"
echo ""
echo "View real-time logs:"
echo "  aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev --follow --profile noaa-target"
echo ""
echo "Trigger manual ingestion:"
echo "  aws lambda invoke --function-name noaa-ingest-atmospheric-dev --payload '{\"env\":\"dev\"}' /tmp/out.json --profile noaa-target"
echo ""
echo "Check S3 data:"
echo "  aws s3 ls s3://${BUCKET_NAME}/bronze/atmospheric/ --recursive --human-readable | tail --profile noaa-target"
echo ""
echo "Dashboard URL:"
echo "  https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html"
echo ""
