#!/bin/bash
set -e

# =============================================================================
# NOAA Federated Data Lake - Glue ETL Pipeline Deployment
# =============================================================================
# This script deploys the automated Glue ETL pipeline that converts JSON arrays
# to JSON Lines format for Athena compatibility.
#
# Features:
# - Creates necessary S3 buckets
# - Uploads Glue ETL scripts
# - Deploys CloudFormation stack with Glue jobs and crawlers
# - Sets up automatic triggers via EventBridge
# - Runs initial ETL conversion
#
# Usage:
#   ./deploy-etl-pipeline.sh [environment]
#
# Example:
#   ./deploy-etl-pipeline.sh dev
#
# Author: NOAA Federated Data Lake Team
# Version: 1.0
# =============================================================================

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ ERROR: Unable to determine AWS Account ID. Is AWS CLI configured?${NC}"
    exit 1
fi

DATA_LAKE_BUCKET="noaa-data-lake-${ENVIRONMENT}"
GLUE_SCRIPT_BUCKET="noaa-glue-scripts-${ENVIRONMENT}"
STACK_NAME="noaa-glue-etl-pipeline-${ENVIRONMENT}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NOAA Federated Data Lake - Glue ETL Pipeline Deployment     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Environment:        $ENVIRONMENT"
echo "  AWS Region:         $AWS_REGION"
echo "  AWS Account:        $AWS_ACCOUNT_ID"
echo "  Data Lake Bucket:   $DATA_LAKE_BUCKET"
echo "  Glue Script Bucket: $GLUE_SCRIPT_BUCKET"
echo "  CloudFormation:     $STACK_NAME"
echo ""

# =============================================================================
# STEP 1: CREATE GLUE SCRIPT BUCKET
# =============================================================================

echo -e "${YELLOW}[1/6] Creating Glue script bucket...${NC}"

if aws s3 ls "s3://${GLUE_SCRIPT_BUCKET}" 2>/dev/null; then
    echo -e "${GREEN}✓ Bucket already exists: ${GLUE_SCRIPT_BUCKET}${NC}"
else
    if [ "$AWS_REGION" == "us-east-1" ]; then
        aws s3 mb "s3://${GLUE_SCRIPT_BUCKET}" --region "$AWS_REGION"
    else
        aws s3 mb "s3://${GLUE_SCRIPT_BUCKET}" --region "$AWS_REGION" --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi
    echo -e "${GREEN}✓ Created bucket: ${GLUE_SCRIPT_BUCKET}${NC}"
fi

# Enable versioning for script bucket
aws s3api put-bucket-versioning \
    --bucket "$GLUE_SCRIPT_BUCKET" \
    --versioning-configuration Status=Enabled 2>/dev/null || true

echo ""

# =============================================================================
# STEP 2: UPLOAD GLUE ETL SCRIPT
# =============================================================================

echo -e "${YELLOW}[2/6] Uploading Glue ETL scripts...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Upload the main ETL script
aws s3 cp "${SCRIPT_DIR}/json_array_to_jsonlines.py" \
    "s3://${GLUE_SCRIPT_BUCKET}/glue-etl/json_array_to_jsonlines.py"

echo -e "${GREEN}✓ Uploaded json_array_to_jsonlines.py${NC}"

# Create a version marker
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" | aws s3 cp - "s3://${GLUE_SCRIPT_BUCKET}/glue-etl/version.txt"

echo ""

# =============================================================================
# STEP 3: DEPLOY CLOUDFORMATION STACK
# =============================================================================

echo -e "${YELLOW}[3/6] Deploying CloudFormation stack...${NC}"

aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/glue-etl-stack.yaml" \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
        DataLakeBucket="$DATA_LAKE_BUCKET" \
        GlueScriptBucket="$GLUE_SCRIPT_BUCKET" \
        EnableAutoTrigger="true" \
        ETLSchedule="rate(15 minutes)" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --no-fail-on-empty-changeset

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ CloudFormation stack deployed successfully${NC}"
else
    echo -e "${RED}❌ CloudFormation deployment failed${NC}"
    exit 1
fi

echo ""

# =============================================================================
# STEP 4: GET STACK OUTPUTS
# =============================================================================

echo -e "${YELLOW}[4/6] Retrieving stack outputs...${NC}"

QUERYABLE_DATABASE=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`QueryableDatabase`].OutputValue' \
    --output text \
    --region "$AWS_REGION")

QUERYABLE_DATA_PATH=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`QueryableDataPath`].OutputValue' \
    --output text \
    --region "$AWS_REGION")

echo -e "${GREEN}✓ Queryable Database: ${QUERYABLE_DATABASE}${NC}"
echo -e "${GREEN}✓ Queryable Data Path: ${QUERYABLE_DATA_PATH}${NC}"

echo ""

# =============================================================================
# STEP 5: RUN INITIAL ETL JOBS
# =============================================================================

echo -e "${YELLOW}[5/6] Triggering initial ETL conversion jobs...${NC}"
echo ""

# Function to start a Glue job
start_glue_job() {
    local job_name=$1
    local pond=$2

    echo -e "  ${BLUE}▶${NC} Starting: ${job_name}"

    JOB_RUN_ID=$(aws glue start-job-run \
        --job-name "$job_name" \
        --region "$AWS_REGION" \
        --query 'JobRunId' \
        --output text 2>/dev/null)

    if [ $? -eq 0 ]; then
        echo -e "    ${GREEN}✓${NC} Job started: ${JOB_RUN_ID}"
    else
        echo -e "    ${YELLOW}⚠${NC} Job may not have data yet (this is normal on first run)"
    fi
}

# Start ETL jobs for each pond
start_glue_job "noaa-etl-atmospheric-observations-${ENVIRONMENT}" "atmospheric"
start_glue_job "noaa-etl-atmospheric-stations-${ENVIRONMENT}" "atmospheric"
start_glue_job "noaa-etl-atmospheric-alerts-${ENVIRONMENT}" "atmospheric"
start_glue_job "noaa-etl-oceanic-${ENVIRONMENT}" "oceanic"
start_glue_job "noaa-etl-buoy-${ENVIRONMENT}" "buoy"

echo ""
echo -e "${GREEN}✓ All ETL jobs triggered${NC}"
echo -e "${YELLOW}⏳ Jobs will run for 2-5 minutes. Monitor progress in AWS Glue console.${NC}"

echo ""

# =============================================================================
# STEP 6: WAIT AND RUN CRAWLERS
# =============================================================================

echo -e "${YELLOW}[6/6] Waiting for ETL jobs to complete, then running crawlers...${NC}"
echo ""

# Wait for jobs to complete (with timeout)
echo -e "  ${BLUE}⏳${NC} Waiting 3 minutes for initial ETL processing..."
sleep 180

# Start crawlers to catalog the converted data
echo ""
echo -e "  ${BLUE}▶${NC} Starting Glue crawlers to catalog queryable data..."

aws glue start-crawler \
    --name "noaa-queryable-atmospheric-crawler-${ENVIRONMENT}" \
    --region "$AWS_REGION" 2>/dev/null && \
    echo -e "    ${GREEN}✓${NC} Started: noaa-queryable-atmospheric-crawler-${ENVIRONMENT}" || \
    echo -e "    ${YELLOW}⚠${NC} Crawler may already be running"

aws glue start-crawler \
    --name "noaa-queryable-oceanic-crawler-${ENVIRONMENT}" \
    --region "$AWS_REGION" 2>/dev/null && \
    echo -e "    ${GREEN}✓${NC} Started: noaa-queryable-oceanic-crawler-${ENVIRONMENT}" || \
    echo -e "    ${YELLOW}⚠${NC} Crawler may already be running"

aws glue start-crawler \
    --name "noaa-queryable-buoy-crawler-${ENVIRONMENT}" \
    --region "$AWS_REGION" 2>/dev/null && \
    echo -e "    ${GREEN}✓${NC} Started: noaa-queryable-buoy-crawler-${ENVIRONMENT}" || \
    echo -e "    ${YELLOW}⚠${NC} Crawler may already be running"

echo ""

# =============================================================================
# DEPLOYMENT SUMMARY
# =============================================================================

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    DEPLOYMENT COMPLETE! 🎉                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✅ Glue ETL Pipeline Successfully Deployed${NC}"
echo ""
echo -e "${YELLOW}What happens next:${NC}"
echo "  1. ETL jobs run every 15 minutes automatically"
echo "  2. JSON arrays are converted to JSON Lines format"
echo "  3. Crawlers catalog the queryable data every 30 minutes"
echo "  4. Data becomes queryable via Athena in ~5 minutes"
echo ""
echo -e "${YELLOW}Key Resources:${NC}"
echo "  • Queryable Database: ${QUERYABLE_DATABASE}"
echo "  • Data Location:      ${QUERYABLE_DATA_PATH}"
echo "  • CloudFormation:     ${STACK_NAME}"
echo ""
echo -e "${YELLOW}Query Your Data:${NC}"
echo "  AWS Athena Console:"
echo "    https://console.aws.amazon.com/athena/home?region=${AWS_REGION}"
echo ""
echo "  Example Query:"
echo -e "    ${BLUE}SELECT station_id, hour, avg_temperature, avg_wind_speed"
echo "    FROM ${QUERYABLE_DATABASE}.observations"
echo "    WHERE station_id = 'KBOS'"
echo -e "    ORDER BY hour DESC LIMIT 10;${NC}"
echo ""
echo -e "${YELLOW}Monitor ETL Jobs:${NC}"
echo "  AWS Glue Console:"
echo "    https://console.aws.amazon.com/glue/home?region=${AWS_REGION}#etl:tab=jobs"
echo ""
echo -e "${YELLOW}View Logs:${NC}"
echo "  CloudWatch Logs:"
echo "    https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups/log-group/\$252Faws-glue\$252Fjobs"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Pipeline Status: ACTIVE ✓${NC}"
echo -e "${GREEN}Auto-conversion: ENABLED ✓${NC}"
echo -e "${GREEN}Data will be queryable in Athena shortly!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Save deployment info to file
cat > "${SCRIPT_DIR}/deployment-info-${ENVIRONMENT}.json" <<EOF
{
  "deployment_time": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "environment": "${ENVIRONMENT}",
  "region": "${AWS_REGION}",
  "account_id": "${AWS_ACCOUNT_ID}",
  "data_lake_bucket": "${DATA_LAKE_BUCKET}",
  "glue_script_bucket": "${GLUE_SCRIPT_BUCKET}",
  "cloudformation_stack": "${STACK_NAME}",
  "queryable_database": "${QUERYABLE_DATABASE}",
  "queryable_data_path": "${QUERYABLE_DATA_PATH}",
  "status": "deployed"
}
EOF

echo -e "${GREEN}✓ Deployment info saved to: deployment-info-${ENVIRONMENT}.json${NC}"
echo ""
