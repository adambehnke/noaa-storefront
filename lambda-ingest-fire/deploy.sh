#!/bin/bash

################################################################################
# Fire Data Ingestion Lambda Deployment Script
# Deploys Lambda function to ingest NOAA Fire Portal data into Atmospheric Pond
#
# Usage:
#   ./deploy.sh [--env dev|prod] [--profile noaa-target]
#
# Author: NOAA Data Lake Team
# Version: 1.0
################################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;96m'
NC='\033[0m'
BOLD='\033[1m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
ENV="dev"
AWS_PROFILE="noaa-target"
AWS_REGION="us-east-1"
FUNCTION_NAME="noaa-ingest-fire-${ENV}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            FUNCTION_NAME="noaa-ingest-fire-${ENV}"
            shift 2
            ;;
        --profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --env <env>       Environment (dev/prod) [default: dev]"
            echo "  --profile <name>  AWS profile [default: noaa-target]"
            echo "  --help            Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Derived configuration
S3_BUCKET="noaa-federated-lake-899626030376-${ENV}"
ROLE_NAME="noaa-lambda-execution-role-${ENV}"
SCHEDULE_NAME="noaa-ingest-fire-schedule-${ENV}"

echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}  NOAA Fire Data Ingestion Lambda Deployment${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo ""
echo -e "${BLUE}Environment:${NC}      ${ENV}"
echo -e "${BLUE}Function Name:${NC}    ${FUNCTION_NAME}"
echo -e "${BLUE}AWS Profile:${NC}      ${AWS_PROFILE}"
echo -e "${BLUE}AWS Region:${NC}       ${AWS_REGION}"
echo -e "${BLUE}S3 Bucket:${NC}        ${S3_BUCKET}"
echo ""
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo ""

# Verify AWS credentials
echo -e "${YELLOW}[1/8]${NC} Verifying AWS credentials..."
if ! aws sts get-caller-identity --profile "${AWS_PROFILE}" > /dev/null 2>&1; then
    echo -e "${RED}✗ AWS credentials not valid for profile: ${AWS_PROFILE}${NC}"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --profile "${AWS_PROFILE}" --query Account --output text)
echo -e "${GREEN}✓ Authenticated to AWS Account: ${ACCOUNT_ID}${NC}"
echo ""

# Check if S3 bucket exists
echo -e "${YELLOW}[2/8]${NC} Verifying S3 bucket..."
if aws s3 ls "s3://${S3_BUCKET}" --profile "${AWS_PROFILE}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ S3 bucket exists: ${S3_BUCKET}${NC}"
else
    echo -e "${RED}✗ S3 bucket not found: ${S3_BUCKET}${NC}"
    exit 1
fi
echo ""

# Create package directory
echo -e "${YELLOW}[3/8]${NC} Creating deployment package..."
PACKAGE_DIR="${SCRIPT_DIR}/package"
rm -rf "${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}"

# Install dependencies
echo "  - Installing Python dependencies..."
if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    pip install -q -r "${SCRIPT_DIR}/requirements.txt" -t "${PACKAGE_DIR}/" --upgrade
    echo -e "${GREEN}  ✓ Dependencies installed${NC}"
else
    echo -e "${YELLOW}  ⚠ No requirements.txt found, skipping dependencies${NC}"
fi

# Copy Lambda function
echo "  - Copying Lambda function code..."
cp "${SCRIPT_DIR}/lambda_function.py" "${PACKAGE_DIR}/"
echo -e "${GREEN}  ✓ Code copied${NC}"

# Create ZIP file
echo "  - Creating deployment ZIP..."
cd "${PACKAGE_DIR}"
ZIP_FILE="${SCRIPT_DIR}/lambda-fire-ingest.zip"
rm -f "${ZIP_FILE}"
zip -q -r "${ZIP_FILE}" .
cd "${SCRIPT_DIR}"
ZIP_SIZE=$(du -h "${ZIP_FILE}" | cut -f1)
echo -e "${GREEN}✓ Deployment package created: ${ZIP_SIZE}${NC}"
echo ""

# Check if Lambda role exists
echo -e "${YELLOW}[4/8]${NC} Checking IAM role..."
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
if aws iam get-role --role-name "${ROLE_NAME}" --profile "${AWS_PROFILE}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ IAM role exists: ${ROLE_NAME}${NC}"
else
    echo -e "${YELLOW}⚠ IAM role not found, attempting to create...${NC}"

    # Create trust policy
    TRUST_POLICY='{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'

    aws iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document "${TRUST_POLICY}" \
        --description "Execution role for NOAA data lake Lambda functions" \
        --profile "${AWS_PROFILE}" > /dev/null

    # Attach policies
    aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
        --profile "${AWS_PROFILE}"

    aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonS3FullAccess" \
        --profile "${AWS_PROFILE}"

    aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonSSMFullAccess" \
        --profile "${AWS_PROFILE}"

    echo -e "${GREEN}✓ IAM role created: ${ROLE_NAME}${NC}"
    echo -e "${YELLOW}  Waiting 10 seconds for IAM role to propagate...${NC}"
    sleep 10
fi
echo ""

# Deploy Lambda function
echo -e "${YELLOW}[5/8]${NC} Deploying Lambda function..."
if aws lambda get-function --function-name "${FUNCTION_NAME}" --profile "${AWS_PROFILE}" > /dev/null 2>&1; then
    echo "  - Updating existing function..."
    aws lambda update-function-code \
        --function-name "${FUNCTION_NAME}" \
        --zip-file "fileb://${ZIP_FILE}" \
        --profile "${AWS_PROFILE}" \
        --output json > /dev/null

    echo "  - Updating configuration..."
    aws lambda update-function-configuration \
        --function-name "${FUNCTION_NAME}" \
        --runtime python3.12 \
        --handler lambda_function.lambda_handler \
        --timeout 300 \
        --memory-size 512 \
        --environment "Variables={S3_BUCKET=${S3_BUCKET},ENV=${ENV}}" \
        --profile "${AWS_PROFILE}" \
        --output json > /dev/null

    echo -e "${GREEN}✓ Lambda function updated${NC}"
else
    echo "  - Creating new function..."
    aws lambda create-function \
        --function-name "${FUNCTION_NAME}" \
        --runtime python3.12 \
        --role "${ROLE_ARN}" \
        --handler lambda_function.lambda_handler \
        --zip-file "fileb://${ZIP_FILE}" \
        --timeout 300 \
        --memory-size 512 \
        --environment "Variables={S3_BUCKET=${S3_BUCKET},ENV=${ENV}}" \
        --description "Ingests NOAA Fire Portal data into Atmospheric Pond" \
        --profile "${AWS_PROFILE}" \
        --output json > /dev/null

    echo -e "${GREEN}✓ Lambda function created${NC}"
fi
echo ""

# Create/Update EventBridge schedule
echo -e "${YELLOW}[6/8]${NC} Configuring EventBridge schedule..."
LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

# Check if rule exists
if aws events describe-rule --name "${SCHEDULE_NAME}" --profile "${AWS_PROFILE}" > /dev/null 2>&1; then
    echo "  - Updating existing schedule..."
    aws events put-rule \
        --name "${SCHEDULE_NAME}" \
        --schedule-expression "rate(15 minutes)" \
        --state ENABLED \
        --description "Trigger fire data ingestion every 15 minutes" \
        --profile "${AWS_PROFILE}" \
        --output json > /dev/null
else
    echo "  - Creating new schedule..."
    aws events put-rule \
        --name "${SCHEDULE_NAME}" \
        --schedule-expression "rate(15 minutes)" \
        --state ENABLED \
        --description "Trigger fire data ingestion every 15 minutes" \
        --profile "${AWS_PROFILE}" \
        --output json > /dev/null
fi

# Add Lambda permission for EventBridge
echo "  - Adding EventBridge permission to Lambda..."
aws lambda add-permission \
    --function-name "${FUNCTION_NAME}" \
    --statement-id "${SCHEDULE_NAME}-permission" \
    --action "lambda:InvokeFunction" \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${SCHEDULE_NAME}" \
    --profile "${AWS_PROFILE}" \
    --output json > /dev/null 2>&1 || true

# Add target to EventBridge rule
echo "  - Linking schedule to Lambda function..."
aws events put-targets \
    --rule "${SCHEDULE_NAME}" \
    --targets "Id=1,Arn=${LAMBDA_ARN}" \
    --profile "${AWS_PROFILE}" \
    --output json > /dev/null

echo -e "${GREEN}✓ EventBridge schedule configured (every 15 minutes)${NC}"
echo ""

# Test Lambda function
echo -e "${YELLOW}[7/8]${NC} Testing Lambda function..."
TEST_EVENT='{"source":"deployment-test","time":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}'
TEST_OUTPUT="${SCRIPT_DIR}/test-output.json"

echo "  - Invoking function..."
if aws lambda invoke \
    --function-name "${FUNCTION_NAME}" \
    --payload "${TEST_EVENT}" \
    --profile "${AWS_PROFILE}" \
    "${TEST_OUTPUT}" > /dev/null 2>&1; then

    if [ -f "${TEST_OUTPUT}" ]; then
        STATUS_CODE=$(cat "${TEST_OUTPUT}" | jq -r '.statusCode' 2>/dev/null || echo "unknown")
        if [ "$STATUS_CODE" = "200" ] || [ "$STATUS_CODE" = "207" ]; then
            echo -e "${GREEN}✓ Lambda function test successful${NC}"

            # Show summary
            TOTAL_DETECTIONS=$(cat "${TEST_OUTPUT}" | jq -r '.body | fromjson | .total_detections' 2>/dev/null || echo "0")
            COLLECTIONS_COUNT=$(cat "${TEST_OUTPUT}" | jq -r '.body | fromjson | .collections_processed | length' 2>/dev/null || echo "0")
            echo "  - Detections found: ${TOTAL_DETECTIONS}"
            echo "  - Collections processed: ${COLLECTIONS_COUNT}"
        else
            echo -e "${YELLOW}⚠ Lambda returned status code: ${STATUS_CODE}${NC}"
            echo "  (This may be normal if no new fire data is available)"
        fi
    fi
else
    echo -e "${YELLOW}⚠ Lambda test returned non-zero exit code${NC}"
    echo "  (Check CloudWatch logs for details)"
fi
echo ""

# Cleanup
echo -e "${YELLOW}[8/8]${NC} Cleaning up..."
rm -rf "${PACKAGE_DIR}"
rm -f "${TEST_OUTPUT}"
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Summary
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo -e "${CYAN}${BOLD}  Deployment Complete!${NC}"
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo ""
echo -e "${GREEN}✓ Lambda Function:${NC}    ${FUNCTION_NAME}"
echo -e "${GREEN}✓ Schedule:${NC}           Every 15 minutes"
echo -e "${GREEN}✓ Data Pond:${NC}          Atmospheric (fire)"
echo -e "${GREEN}✓ Bronze Path:${NC}        s3://${S3_BUCKET}/bronze/atmospheric/fire/"
echo -e "${GREEN}✓ Gold Path:${NC}          s3://${S3_BUCKET}/gold/atmospheric/fire/"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Monitor logs:"
echo "   ${CYAN}aws logs tail /aws/lambda/${FUNCTION_NAME} --follow --profile ${AWS_PROFILE}${NC}"
echo ""
echo "2. Check S3 for data:"
echo "   ${CYAN}aws s3 ls s3://${S3_BUCKET}/bronze/atmospheric/fire/ --recursive --profile ${AWS_PROFILE}${NC}"
echo ""
echo "3. View recent detections:"
echo "   ${CYAN}aws s3 cp s3://${S3_BUCKET}/gold/atmospheric/fire/date=\$(date +%Y-%m-%d)/ - --recursive --profile ${AWS_PROFILE}${NC}"
echo ""
echo "4. Invoke manually (optional):"
echo "   ${CYAN}aws lambda invoke --function-name ${FUNCTION_NAME} /tmp/out.json --profile ${AWS_PROFILE}${NC}"
echo ""
echo -e "${CYAN}${BOLD}================================================================${NC}"
echo ""
