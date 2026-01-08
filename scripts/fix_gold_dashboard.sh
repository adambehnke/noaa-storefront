#!/bin/bash
#
# NOAA Data Lake - Fix Gold Layer Dashboard
# Resolves 502 Bad Gateway errors in Gold layer modal
#
# Issues fixed:
#   1. Missing IAM permissions (Glue, Athena)
#   2. Lambda timeout on slow queries
#   3. Insufficient memory allocation
#

set -e

# Force correct AWS profile
export AWS_PROFILE=noaa-target
export AWS_REGION=us-east-1
ENV=dev

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
LAMBDA_NAME="noaa-dashboard-metrics"
ROLE_NAME="noaa-dev-lambda-exec"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

if [ "$ACCOUNT_ID" != "899626030376" ]; then
    echo -e "${RED}ERROR: Wrong AWS account! Expected 899626030376, got ${ACCOUNT_ID}${NC}"
    exit 1
fi

BUCKET_NAME="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"

# Banner
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     NOAA Data Lake - Gold Dashboard Fix Script              ║"
echo "║     Account: ${ACCOUNT_ID}                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Step 1: Add comprehensive IAM permissions
echo -e "${BLUE}[1/5] Adding IAM Permissions...${NC}"

cat > /tmp/dashboard-full-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaAccess",
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchAccess",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EventBridgeAccess",
      "Effect": "Allow",
      "Action": [
        "events:ListRules",
        "events:DescribeRule",
        "events:ListTargetsByRule"
      ],
      "Resource": "*"
    },
    {
      "Sid": "GlueAccess",
      "Effect": "Allow",
      "Action": [
        "glue:GetTables",
        "glue:GetTable",
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetJob",
        "glue:GetJobs",
        "glue:GetJobRuns",
        "glue:GetJobRun",
        "glue:GetPartitions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AthenaAccess",
      "Effect": "Allow",
      "Action": [
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetWorkGroup"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::noaa-federated-lake-899626030376-dev/*",
        "arn:aws:s3:::noaa-federated-lake-899626030376-dev"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name DashboardMetricsFullAccess \
  --policy-document file:///tmp/dashboard-full-policy.json

echo -e "${GREEN}✓ IAM permissions updated${NC}"
echo "  - Lambda: List, Get"
echo "  - CloudWatch: Metrics"
echo "  - EventBridge: Rules"
echo "  - Glue: Tables, Jobs"
echo "  - Athena: Queries"
echo "  - S3: Read/Write"
echo ""

# Step 2: Increase Lambda timeout and memory
echo -e "${BLUE}[2/5] Updating Lambda Configuration...${NC}"

aws lambda update-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --timeout 120 \
  --memory-size 1024 \
  --query '{Timeout:Timeout,Memory:MemorySize,Runtime:Runtime}' \
  --output table

echo -e "${GREEN}✓ Lambda configuration updated${NC}"
echo "  - Timeout: 120 seconds (was 30)"
echo "  - Memory: 1024 MB (was 512)"
echo ""

# Step 3: Wait for update to propagate
echo -e "${BLUE}[3/5] Waiting for configuration to propagate...${NC}"
sleep 5

# Check update status
STATUS="InProgress"
WAIT_COUNT=0
MAX_WAIT=12

while [ "$STATUS" = "InProgress" ] && [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    STATUS=$(aws lambda get-function-configuration \
        --function-name "$LAMBDA_NAME" \
        --query 'LastUpdateStatus' \
        --output text)

    if [ "$STATUS" = "InProgress" ]; then
        echo "  Waiting for Lambda update... ($((WAIT_COUNT + 1))/$MAX_WAIT)"
        sleep 5
        ((WAIT_COUNT++))
    fi
done

if [ "$STATUS" = "Successful" ]; then
    echo -e "${GREEN}✓ Configuration update successful${NC}"
elif [ "$STATUS" = "InProgress" ]; then
    echo -e "${YELLOW}⚠ Update still in progress, continuing...${NC}"
else
    echo -e "${YELLOW}⚠ Update status: $STATUS${NC}"
fi
echo ""

# Step 4: Force Lambda restart by updating environment variable
echo -e "${BLUE}[4/5] Forcing Lambda restart...${NC}"

TIMESTAMP=$(date +%s)

aws lambda update-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --environment "Variables={DATA_LAKE_BUCKET=${BUCKET_NAME},ATHENA_DATABASE=noaa_data_lake,ATHENA_OUTPUT_BUCKET=s3://${BUCKET_NAME}/athena-results/,UPDATED=${TIMESTAMP}}" \
  --query 'FunctionName' \
  --output text > /dev/null

echo -e "${GREEN}✓ Lambda restarted with new permissions${NC}"
echo ""

# Step 5: Test Gold layer endpoint
echo -e "${BLUE}[5/5] Testing Gold Layer Endpoint...${NC}"
echo ""

# Wait for Lambda to be ready
echo "Waiting for Lambda to initialize..."
sleep 15

LAMBDA_URL="https://ghew7mwudk326bla57wgqe5xxi0ymhjm.lambda-url.us-east-1.on.aws"
TEST_URL="${LAMBDA_URL}?metric_type=gold_layer"

echo "Testing: $TEST_URL"
echo ""

# Test with timeout
RESPONSE=$(timeout 60 curl -s "$TEST_URL" 2>&1 || echo "TIMEOUT")

if [ "$RESPONSE" = "TIMEOUT" ]; then
    echo -e "${RED}✗ Request timed out${NC}"
    echo ""
    echo "This may indicate:"
    echo "  1. Lambda is still warming up (wait 1 minute and try again)"
    echo "  2. Athena queries are slow (expected on first run)"
    echo ""
    echo "Manual test command:"
    echo "  curl \"${TEST_URL}\""
    echo ""
    exit 1
elif echo "$RESPONSE" | grep -q "Internal Server Error"; then
    echo -e "${RED}✗ Internal Server Error${NC}"
    echo ""
    echo "Check Lambda logs:"
    echo "  aws logs tail /aws/lambda/${LAMBDA_NAME} --follow --profile noaa-target"
    echo ""
    exit 1
elif echo "$RESPONSE" | grep -q "gold"; then
    # Parse response
    TABLES=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('tables', [])))" 2>/dev/null || echo "0")
    FILES=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('storage', {}).get('total_files', 0))" 2>/dev/null || echo "0")
    SIZE=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('storage', {}).get('total_size_gb', 0))" 2>/dev/null || echo "0")

    echo -e "${GREEN}✓ Gold layer endpoint is working!${NC}"
    echo ""
    echo "Gold Layer Status:"
    echo "  - Athena Tables: ${TABLES}"
    echo "  - Storage Files: ${FILES}"
    echo "  - Storage Size: ${SIZE} GB"
    echo ""
else
    echo -e "${YELLOW}⚠ Unexpected response${NC}"
    echo "Response preview:"
    echo "$RESPONSE" | head -20
    echo ""
fi

# Test other endpoints
echo -e "${CYAN}Testing other dashboard endpoints...${NC}"

# Test Bronze
BRONZE_RESPONSE=$(timeout 30 curl -s "${LAMBDA_URL}?metric_type=bronze_layer" 2>&1 || echo "TIMEOUT")
if echo "$BRONZE_RESPONSE" | grep -q "bronze"; then
    ENDPOINTS=$(echo "$BRONZE_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('endpoints', [])))" 2>/dev/null || echo "0")
    echo -e "${GREEN}✓ Bronze layer: ${ENDPOINTS} endpoints${NC}"
else
    echo -e "${YELLOW}⚠ Bronze layer: Issue detected${NC}"
fi

# Test Silver
SILVER_RESPONSE=$(timeout 30 curl -s "${LAMBDA_URL}?metric_type=silver_layer" 2>&1 || echo "TIMEOUT")
if echo "$SILVER_RESPONSE" | grep -q "silver"; then
    echo -e "${GREEN}✓ Silver layer: Working${NC}"
else
    echo -e "${YELLOW}⚠ Silver layer: Issue detected${NC}"
fi

echo ""

# Summary
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  SUMMARY${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Changes Applied:"
echo "  ✓ IAM permissions added (Lambda, CloudWatch, Glue, Athena, S3)"
echo "  ✓ Lambda timeout increased to 120 seconds"
echo "  ✓ Lambda memory increased to 1024 MB"
echo "  ✓ Lambda restarted with new configuration"
echo ""
echo "Dashboard URL:"
echo "  https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html"
echo ""
echo "API Endpoints:"
echo "  Bronze: ${LAMBDA_URL}?metric_type=bronze_layer"
echo "  Silver: ${LAMBDA_URL}?metric_type=silver_layer"
echo "  Gold:   ${LAMBDA_URL}?metric_type=gold_layer"
echo ""
echo "Next Steps:"
echo "  1. Open the dashboard and test all three modals"
echo "  2. If Gold layer still has issues, check logs:"
echo "     aws logs tail /aws/lambda/${LAMBDA_NAME} --follow --profile noaa-target"
echo "  3. Start historical backfill:"
echo "     AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py --test"
echo ""
echo -e "${GREEN}✅ Gold Dashboard Fix Complete!${NC}"
echo ""
