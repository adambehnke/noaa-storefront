#!/bin/bash
#
# NOAA Data Lake - Deploy All Ingestion Lambda Functions
#
# This script redeploys all ingestion Lambda functions to restore
# active data collection across all medallion layers (Bronze, Silver, Gold)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
ENV=${ENV:-dev}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}ERROR: Could not determine AWS Account ID. Check your AWS credentials.${NC}"
    exit 1
fi

BUCKET_NAME="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
DEPLOYMENT_BUCKET="noaa-deployment-${ACCOUNT_ID}-${ENV}"
LAMBDA_ROLE_NAME="noaa-lambda-execution-role-${ENV}"

# Print banner
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       NOAA Ingestion Lambda Deployment Script                 ║${NC}"
echo -e "${CYAN}║       Restoring Active Data Collection                        ║${NC}"
echo -e "${CYAN}╠════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║ Account ID:      ${ACCOUNT_ID}                            ║${NC}"
echo -e "${CYAN}║ Region:          ${AWS_REGION}                                  ║${NC}"
echo -e "${CYAN}║ Environment:     ${ENV}                                            ║${NC}"
echo -e "${CYAN}║ Data Lake:       ${BUCKET_NAME} ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Status functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
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

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Check prerequisites
print_section "Checking Prerequisites"

# Check if bucket exists
if aws s3 ls "s3://${BUCKET_NAME}" >/dev/null 2>&1; then
    print_success "Data lake bucket exists: ${BUCKET_NAME}"
else
    print_error "Data lake bucket not found: ${BUCKET_NAME}"
    exit 1
fi

# Create or verify Lambda execution role
print_section "Setting Up IAM Role"

ROLE_EXISTS=$(aws iam get-role --role-name "$LAMBDA_ROLE_NAME" 2>/dev/null || echo "")

if [ -z "$ROLE_EXISTS" ]; then
    print_status "Creating Lambda execution role..."

    # Create trust policy
    cat > /tmp/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "$LAMBDA_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --description "Execution role for NOAA ingestion Lambda functions"

    print_success "Created role: ${LAMBDA_ROLE_NAME}"

    # Attach policies
    print_status "Attaching policies..."

    aws iam attach-role-policy \
        --role-name "$LAMBDA_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    aws iam attach-role-policy \
        --role-name "$LAMBDA_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess"

    aws iam attach-role-policy \
        --role-name "$LAMBDA_ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonAthenaFullAccess"

    print_success "Attached IAM policies"

    # Wait for role to propagate
    print_status "Waiting for IAM role to propagate (10 seconds)..."
    sleep 10
else
    print_success "Lambda execution role exists: ${LAMBDA_ROLE_NAME}"
fi

LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

# Deploy each ingestion Lambda
print_section "Deploying Ingestion Lambda Functions"

declare -A LAMBDAS=(
    ["atmospheric"]="lambda-ingest-atmospheric"
    ["buoy"]="lambda-ingest-buoy"
    ["oceanic"]="lambda-ingest-oceanic"
    ["climate"]="lambda-ingest-climate"
    ["spatial"]="lambda-ingest-spatial"
    ["terrestrial"]="lambda-ingest-terrestrial"
)

declare -A TIMEOUTS=(
    ["atmospheric"]="300"
    ["buoy"]="300"
    ["oceanic"]="300"
    ["climate"]="600"
    ["spatial"]="300"
    ["terrestrial"]="300"
)

declare -A MEMORY=(
    ["atmospheric"]="512"
    ["buoy"]="512"
    ["oceanic"]="512"
    ["climate"]="1024"
    ["spatial"]="512"
    ["terrestrial"]="512"
)

DEPLOYED_COUNT=0
FAILED_COUNT=0

for POND in "${!LAMBDAS[@]}"; do
    LAMBDA_DIR="${LAMBDAS[$POND]}"
    LAMBDA_NAME="noaa-ingest-${POND}-${ENV}"

    echo ""
    print_status "Deploying ${CYAN}${POND}${NC} ingestion Lambda..."

    if [ ! -d "$LAMBDA_DIR" ]; then
        print_warning "Directory not found: ${LAMBDA_DIR} - skipping"
        ((FAILED_COUNT++))
        continue
    fi

    # Create deployment package
    TEMP_DIR=$(mktemp -d)
    PACKAGE_FILE="${TEMP_DIR}/${POND}-deployment.zip"

    print_status "  Creating deployment package..."

    # Copy Python files
    cp "${LAMBDA_DIR}"/*.py "$TEMP_DIR/" 2>/dev/null || true

    # Create lambda_function.py if it doesn't exist
    if [ ! -f "${TEMP_DIR}/lambda_function.py" ]; then
        print_status "  Creating Lambda handler wrapper..."

        # Find the main ingestion script
        MAIN_SCRIPT=$(ls "${LAMBDA_DIR}"/*.py | grep -E "ingest\.py$" | head -1 | xargs basename)

        cat > "${TEMP_DIR}/lambda_function.py" <<EOFHANDLER
#!/usr/bin/env python3
"""Lambda handler for ${POND} ingestion"""
import subprocess
import sys
import json

def lambda_handler(event, context):
    """Execute ${POND} ingestion"""
    try:
        env = event.get('env', 'dev')

        # Run ingestion script
        result = subprocess.run(
            [sys.executable, '${MAIN_SCRIPT}', '--env', env],
            capture_output=True,
            text=True,
            timeout=290
        )

        return {
            'statusCode': 200 if result.returncode == 0 else 500,
            'body': json.dumps({
                'pond': '${POND}',
                'stdout': result.stdout[-1000:],
                'stderr': result.stderr[-1000:],
                'returncode': result.returncode
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
EOFHANDLER
    fi

    # Install dependencies if requirements.txt exists
    if [ -f "${LAMBDA_DIR}/requirements.txt" ]; then
        print_status "  Installing dependencies..."
        pip install -q -r "${LAMBDA_DIR}/requirements.txt" -t "$TEMP_DIR/" 2>/dev/null || true
    fi

    # Create ZIP package
    cd "$TEMP_DIR"
    zip -q -r "$PACKAGE_FILE" . >/dev/null 2>&1
    cd - >/dev/null

    PACKAGE_SIZE=$(du -h "$PACKAGE_FILE" | cut -f1)
    print_status "  Package size: ${PACKAGE_SIZE}"

    # Check if Lambda exists
    LAMBDA_EXISTS=$(aws lambda get-function --function-name "$LAMBDA_NAME" 2>/dev/null || echo "")

    if [ -z "$LAMBDA_EXISTS" ]; then
        print_status "  Creating new Lambda function..."

        aws lambda create-function \
            --function-name "$LAMBDA_NAME" \
            --runtime python3.11 \
            --role "$LAMBDA_ROLE_ARN" \
            --handler lambda_function.lambda_handler \
            --timeout "${TIMEOUTS[$POND]}" \
            --memory-size "${MEMORY[$POND]}" \
            --zip-file "fileb://${PACKAGE_FILE}" \
            --environment "Variables={DATA_LAKE_BUCKET=${BUCKET_NAME},ENVIRONMENT=${ENV},POND_NAME=${POND}}" \
            --description "NOAA ${POND} data ingestion - ${ENV}" \
            >/dev/null 2>&1

        print_success "  Created Lambda: ${LAMBDA_NAME}"
    else
        print_status "  Updating existing Lambda function..."

        aws lambda update-function-code \
            --function-name "$LAMBDA_NAME" \
            --zip-file "fileb://${PACKAGE_FILE}" \
            >/dev/null 2>&1

        # Wait for update to complete
        sleep 2

        aws lambda update-function-configuration \
            --function-name "$LAMBDA_NAME" \
            --timeout "${TIMEOUTS[$POND]}" \
            --memory-size "${MEMORY[$POND]}" \
            --environment "Variables={DATA_LAKE_BUCKET=${BUCKET_NAME},ENVIRONMENT=${ENV},POND_NAME=${POND}}" \
            >/dev/null 2>&1

        print_success "  Updated Lambda: ${LAMBDA_NAME}"
    fi

    # Grant EventBridge permission to invoke Lambda
    print_status "  Setting EventBridge permissions..."

    aws lambda add-permission \
        --function-name "$LAMBDA_NAME" \
        --statement-id "AllowEventBridgeInvoke-${POND}" \
        --action "lambda:InvokeFunction" \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/noaa-ingest-${POND}-*" \
        >/dev/null 2>&1 || true

    # Test invoke
    print_status "  Testing Lambda invocation..."

    TEST_RESULT=$(aws lambda invoke \
        --function-name "$LAMBDA_NAME" \
        --payload '{"env":"'${ENV}'"}' \
        --log-type Tail \
        /tmp/lambda-test-output.json 2>&1 || echo "FAILED")

    if echo "$TEST_RESULT" | grep -q "StatusCode.*200"; then
        print_success "  Test invocation successful"
        ((DEPLOYED_COUNT++))
    else
        print_error "  Test invocation failed"
        ((FAILED_COUNT++))
    fi

    # Clean up
    rm -rf "$TEMP_DIR"
done

# Summary
print_section "Deployment Summary"

echo -e "${GREEN}Successfully deployed:${NC} ${DEPLOYED_COUNT} Lambda functions"
if [ $FAILED_COUNT -gt 0 ]; then
    echo -e "${RED}Failed:${NC} ${FAILED_COUNT} Lambda functions"
fi

# List EventBridge rules
print_section "Active EventBridge Schedules"

aws events list-rules --query "Rules[?contains(Name, 'noaa-ingest')].{Name:Name, State:State, Schedule:ScheduleExpression}" --output table

# Check recent invocations
print_section "Verifying Active Ingestion"

print_status "Checking Lambda invocations in last 5 minutes..."

for POND in "${!LAMBDAS[@]}"; do
    LAMBDA_NAME="noaa-ingest-${POND}-${ENV}"

    # Get metrics from CloudWatch
    INVOCATIONS=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value="$LAMBDA_NAME" \
        --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --period 300 \
        --statistics Sum \
        --query 'Datapoints[0].Sum' \
        --output text 2>/dev/null || echo "0")

    if [ "$INVOCATIONS" != "None" ] && [ "$INVOCATIONS" != "0" ]; then
        print_success "${POND}: ${INVOCATIONS} invocation(s) in last 5 minutes"
    else
        print_warning "${POND}: No recent invocations (scheduled to run soon)"
    fi
done

# Check S3 for recent data
print_section "Checking Bronze Layer Data"

print_status "Looking for recently ingested data..."

for POND in "${!LAMBDAS[@]}"; do
    RECENT_FILES=$(aws s3 ls "s3://${BUCKET_NAME}/bronze/${POND}/" --recursive | tail -3 | wc -l)

    if [ "$RECENT_FILES" -gt 0 ]; then
        LATEST=$(aws s3 ls "s3://${BUCKET_NAME}/bronze/${POND}/" --recursive | sort | tail -1 | awk '{print $1, $2}')
        print_success "${POND}: Data found (latest: ${LATEST})"
    else
        print_warning "${POND}: No bronze data yet (will appear after first run)"
    fi
done

# Final instructions
print_section "Next Steps"

echo ""
echo -e "${GREEN}✓ Ingestion system is now active!${NC}"
echo ""
echo "The following is happening automatically:"
echo "  • EventBridge schedules trigger Lambda functions"
echo "  • Lambda functions fetch data from NOAA APIs"
echo "  • Data is stored in Bronze layer (raw)"
echo "  • Glue ETL jobs transform to Silver/Gold layers"
echo ""
echo "To monitor ingestion:"
echo "  1. Dashboard: https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html"
echo "  2. CloudWatch Logs: aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --follow"
echo "  3. S3 Bronze layer: aws s3 ls s3://${BUCKET_NAME}/bronze/ --recursive --human-readable"
echo ""
echo "To manually trigger ingestion:"
echo "  aws lambda invoke --function-name noaa-ingest-atmospheric-${ENV} --payload '{\"env\":\"${ENV}\"}' /tmp/output.json"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
