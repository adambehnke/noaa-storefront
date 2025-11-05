#!/bin/bash

################################################################################
# NOAA Federated Data Lake - Complete Deployment Script
#
# This script deploys the entire NOAA data infrastructure to AWS:
# - S3 buckets for data lake (Bronze/Silver/Gold layers)
# - Glue Catalog databases and tables
# - Glue ETL jobs
# - Lambda functions (AI Query, Data API)
# - API Gateway
# - ElastiCache Redis
# - Step Functions pipeline
# - CloudWatch Events
#
# Prerequisites:
# - AWS CLI configured with appropriate credentials
# - jq installed (for JSON parsing)
# - zip installed (for packaging Lambda functions)
# - Python 3.9+ installed
#
# Usage:
#   ./deploy.sh [environment] [region]
#
# Example:
#   ./deploy.sh dev us-east-1
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-us-east-1}
STACK_NAME="noaa-federated-lake-${ENVIRONMENT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  NOAA Federated Data Lake Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "Environment:    ${GREEN}${ENVIRONMENT}${NC}"
echo -e "Region:         ${GREEN}${AWS_REGION}${NC}"
echo -e "Account ID:     ${GREEN}${AWS_ACCOUNT_ID}${NC}"
echo -e "Stack Name:     ${GREEN}${STACK_NAME}${NC}"
echo ""

# Function to print status messages
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install it first (brew install jq or apt-get install jq)"
        exit 1
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    log_success "All prerequisites met"
}

# Function to create Lambda deployment packages
package_lambda_functions() {
    log_info "Packaging Lambda functions..."

    mkdir -p "${SCRIPT_DIR}/lambda-packages"

    # Package AI Query Lambda
    log_info "  → Packaging ai_query_handler..."
    cd "${SCRIPT_DIR}"

    # Install dependencies
    if [ -f "requirements-lambda.txt" ]; then
        pip3 install -r requirements-lambda.txt -t "${SCRIPT_DIR}/lambda-packages/ai-query-package" --quiet
    fi

    # Copy handler
    cp ai_query_handler.py "${SCRIPT_DIR}/lambda-packages/ai-query-package/"

    # Create zip
    cd "${SCRIPT_DIR}/lambda-packages/ai-query-package"
    zip -r ../ai_query_handler.zip . -q
    cd "${SCRIPT_DIR}"

    log_success "  AI Query Lambda packaged"

    # Package Data API Lambda
    log_info "  → Packaging data_api_handler..."
    mkdir -p "${SCRIPT_DIR}/lambda-packages/data-api-package"

    # Install redis dependency
    pip3 install redis -t "${SCRIPT_DIR}/lambda-packages/data-api-package" --quiet

    # Copy handler
    cp data_api_handler.py "${SCRIPT_DIR}/lambda-packages/data-api-package/"

    # Create zip
    cd "${SCRIPT_DIR}/lambda-packages/data-api-package"
    zip -r ../data_api_handler.zip . -q
    cd "${SCRIPT_DIR}"

    log_success "  Data API Lambda packaged"
    log_success "Lambda functions packaged successfully"
}

# Function to upload code to S3
upload_code_to_s3() {
    log_info "Uploading Lambda code and Glue scripts to S3..."

    # Create temporary bucket for deployment artifacts
    TEMP_BUCKET="noaa-deployment-${AWS_ACCOUNT_ID}-${ENVIRONMENT}"

    # Check if bucket exists, create if not
    if ! aws s3 ls "s3://${TEMP_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
        log_info "Using existing deployment bucket: ${TEMP_BUCKET}"
    else
        log_info "Creating deployment bucket: ${TEMP_BUCKET}"
        aws s3 mb "s3://${TEMP_BUCKET}" --region "${AWS_REGION}"
    fi

    # Upload Lambda packages
    log_info "  → Uploading Lambda packages..."
    aws s3 cp "${SCRIPT_DIR}/lambda-packages/ai_query_handler.zip" \
        "s3://${TEMP_BUCKET}/lambda/ai_query_handler.zip"
    aws s3 cp "${SCRIPT_DIR}/lambda-packages/data_api_handler.zip" \
        "s3://${TEMP_BUCKET}/lambda/data_api_handler.zip"

    # Upload Glue scripts
    log_info "  → Uploading Glue ETL scripts..."
    aws s3 cp "${SCRIPT_DIR}/scripts/bronze_to_silver.py" \
        "s3://${TEMP_BUCKET}/glue-scripts/bronze_to_silver.py"
    aws s3 cp "${SCRIPT_DIR}/scripts/silver_to_gold.py" \
        "s3://${TEMP_BUCKET}/glue-scripts/silver_to_gold.py"
    aws s3 cp "${SCRIPT_DIR}/scripts/bronze_ingest_nws_enhanced.py" \
        "s3://${TEMP_BUCKET}/glue-scripts/bronze_ingest_nws.py"
    aws s3 cp "${SCRIPT_DIR}/scripts/bronze_ingest_tides.py" \
        "s3://${TEMP_BUCKET}/glue-scripts/bronze_ingest_tides.py"
    aws s3 cp "${SCRIPT_DIR}/scripts/bronze_ingest_cdo.py" \
        "s3://${TEMP_BUCKET}/glue-scripts/bronze_ingest_cdo.py"

    log_success "Code uploaded to S3"

    echo "${TEMP_BUCKET}" > "${SCRIPT_DIR}/.deployment-bucket"
}

# Function to deploy CloudFormation stack
deploy_cloudformation() {
    log_info "Deploying CloudFormation stack..."

    TEMP_BUCKET=$(cat "${SCRIPT_DIR}/.deployment-bucket")

    # Get NOAA CDO token from environment or prompt
    if [ -z "${NOAA_CDO_TOKEN}" ]; then
        log_warning "NOAA_CDO_TOKEN not set in environment"
        read -p "Enter NOAA CDO API Token (or press Enter to skip): " NOAA_CDO_TOKEN
        NOAA_CDO_TOKEN=${NOAA_CDO_TOKEN:-"CHANGEME"}
    fi

    # Update CloudFormation template to use deployment bucket
    sed "s/\${LambdaCodeBucket}/${TEMP_BUCKET}/g" \
        "${SCRIPT_DIR}/noaa-complete-stack.yaml" > \
        "${SCRIPT_DIR}/noaa-complete-stack-processed.yaml"

    # Deploy stack
    log_info "  → Creating/updating stack (this may take 10-15 minutes)..."

    aws cloudformation deploy \
        --template-file "${SCRIPT_DIR}/noaa-complete-stack-processed.yaml" \
        --stack-name "${STACK_NAME}" \
        --parameter-overrides \
            Environment="${ENVIRONMENT}" \
            NOAACDOToken="${NOAA_CDO_TOKEN}" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${AWS_REGION}" \
        --no-fail-on-empty-changeset

    log_success "CloudFormation stack deployed"
}

# Function to get stack outputs
get_stack_outputs() {
    log_info "Retrieving stack outputs..."

    aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs' \
        --output json > "${SCRIPT_DIR}/stack-outputs.json"

    log_success "Stack outputs saved to stack-outputs.json"
}

# Function to test deployment
test_deployment() {
    log_info "Testing deployment..."

    # Get API endpoint
    API_ENDPOINT=$(jq -r '.[] | select(.OutputKey=="APIEndpoint") | .OutputValue' \
        "${SCRIPT_DIR}/stack-outputs.json")

    if [ -z "${API_ENDPOINT}" ] || [ "${API_ENDPOINT}" == "null" ]; then
        log_warning "API endpoint not found in stack outputs"
        return
    fi

    log_info "  → Testing API endpoint: ${API_ENDPOINT}"

    # Test health check
    log_info "  → Testing health check..."
    HEALTH_RESPONSE=$(curl -s "${API_ENDPOINT}/data?ping=true")

    if echo "${HEALTH_RESPONSE}" | jq -e '.status == "healthy"' > /dev/null; then
        log_success "  Health check passed"
    else
        log_warning "  Health check returned unexpected response: ${HEALTH_RESPONSE}"
    fi
}

# Function to trigger initial data ingestion
trigger_ingestion() {
    log_info "Triggering initial data ingestion..."

    STATE_MACHINE_ARN=$(jq -r '.[] | select(.OutputKey=="StateMachineArn") | .OutputValue' \
        "${SCRIPT_DIR}/stack-outputs.json")

    if [ -z "${STATE_MACHINE_ARN}" ] || [ "${STATE_MACHINE_ARN}" == "null" ]; then
        log_warning "State machine ARN not found"
        return
    fi

    log_info "  → Starting Step Functions execution..."
    EXECUTION_ARN=$(aws stepfunctions start-execution \
        --state-machine-arn "${STATE_MACHINE_ARN}" \
        --region "${AWS_REGION}" \
        --query 'executionArn' \
        --output text)

    log_success "  Execution started: ${EXECUTION_ARN}"
    log_info "  Monitor at: https://${AWS_REGION}.console.aws.amazon.com/states/home?region=${AWS_REGION}#/executions/details/${EXECUTION_ARN}"
}

# Function to print summary
print_summary() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  Deployment Summary${NC}"
    echo -e "${BLUE}================================================${NC}"

    if [ -f "${SCRIPT_DIR}/stack-outputs.json" ]; then
        # Data Lake Bucket
        DATA_LAKE_BUCKET=$(jq -r '.[] | select(.OutputKey=="DataLakeBucketName") | .OutputValue' \
            "${SCRIPT_DIR}/stack-outputs.json")
        echo -e "Data Lake Bucket:   ${GREEN}${DATA_LAKE_BUCKET}${NC}"

        # API Endpoint
        API_ENDPOINT=$(jq -r '.[] | select(.OutputKey=="APIEndpoint") | .OutputValue' \
            "${SCRIPT_DIR}/stack-outputs.json")
        echo -e "API Endpoint:       ${GREEN}${API_ENDPOINT}${NC}"

        # Redis Endpoint
        REDIS_ENDPOINT=$(jq -r '.[] | select(.OutputKey=="RedisEndpoint") | .OutputValue' \
            "${SCRIPT_DIR}/stack-outputs.json")
        echo -e "Redis Endpoint:     ${GREEN}${REDIS_ENDPOINT}${NC}"

        # Databases
        echo -e "Bronze Database:    ${GREEN}noaa_bronze_${ENVIRONMENT}${NC}"
        echo -e "Silver Database:    ${GREEN}noaa_silver_${ENVIRONMENT}${NC}"
        echo -e "Gold Database:      ${GREEN}noaa_gold_${ENVIRONMENT}${NC}"
    fi

    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "1. Monitor the initial data ingestion in Step Functions console"
    echo -e "2. Query data via API: ${GREEN}curl ${API_ENDPOINT}/data?service=atmospheric&limit=10${NC}"
    echo -e "3. Test AI query: ${GREEN}curl -X POST ${API_ENDPOINT}/query -d '{\"action\":\"ai_query\",\"question\":\"Show me recent weather alerts\"}'${NC}"
    echo -e "4. View data in Athena: https://console.aws.amazon.com/athena/home?region=${AWS_REGION}"
    echo -e "5. Check S3 data: ${GREEN}aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/ --recursive${NC}"
    echo ""
    echo -e "${GREEN}Deployment complete! 🚀${NC}"
    echo ""
}

# Function to cleanup on error
cleanup_on_error() {
    log_error "Deployment failed!"
    log_info "Cleaning up temporary files..."
    rm -rf "${SCRIPT_DIR}/lambda-packages"
    rm -f "${SCRIPT_DIR}/noaa-complete-stack-processed.yaml"
    exit 1
}

# Set trap for errors
trap cleanup_on_error ERR

# Main execution
main() {
    check_prerequisites
    package_lambda_functions
    upload_code_to_s3
    deploy_cloudformation
    get_stack_outputs
    test_deployment

    # Ask user if they want to trigger initial ingestion
    read -p "Trigger initial data ingestion now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        trigger_ingestion
    else
        log_info "Skipping initial ingestion. You can trigger it manually later."
    fi

    print_summary

    # Cleanup temporary files
    rm -rf "${SCRIPT_DIR}/lambda-packages"
    rm -f "${SCRIPT_DIR}/noaa-complete-stack-processed.yaml"
}

# Run main function
main
