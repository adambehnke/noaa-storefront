#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - Environment Configuration
#
# This file contains all environment-specific configuration for the NOAA
# Federated Data Lake. Source this file at the beginning of any script to
# ensure consistent configuration across the project.
#
# Usage:
#   source config/environment.sh
#   source "$(dirname "$0")/../config/environment.sh"
#
# Environment Variables Set:
#   - AWS_PROFILE: AWS CLI profile to use
#   - AWS_ACCOUNT_ID: Target AWS account ID
#   - AWS_REGION: AWS region for deployments
#   - ENVIRONMENT: Environment name (dev/staging/prod)
#   - DATA_LAKE_BUCKET: S3 bucket for data lake
#   - DEPLOYMENT_BUCKET: S3 bucket for deployment artifacts
#   - ATHENA_RESULTS_BUCKET: S3 bucket for Athena query results
#   - LAMBDA_LAYER_BUCKET: S3 bucket for Lambda layers
#   - CHATBOT_BUCKET: S3 bucket for chatbot web interface
#
###############################################################################

# ============================================================================
# CORE CONFIGURATION
# ============================================================================

# AWS Profile - Use noaa-target for account 899626030376
export AWS_PROFILE="${AWS_PROFILE:-noaa-target}"

# Target AWS Account ID (PRODUCTION ACCOUNT)
export AWS_ACCOUNT_ID="899626030376"

# AWS Region
export AWS_REGION="${AWS_REGION:-us-east-1}"

# Environment (dev/staging/prod)
export ENVIRONMENT="${ENVIRONMENT:-dev}"

# Short environment name for compatibility
export ENV="${ENV:-${ENVIRONMENT}}"

# ============================================================================
# DERIVED CONFIGURATIONS
# ============================================================================

# S3 Bucket Names
export DATA_LAKE_BUCKET="noaa-federated-lake-${AWS_ACCOUNT_ID}-${ENV}"
export DEPLOYMENT_BUCKET="noaa-deployment-${AWS_ACCOUNT_ID}-${ENV}"
export ATHENA_RESULTS_BUCKET="noaa-athena-results-${AWS_ACCOUNT_ID}-${ENV}"
export LAMBDA_LAYER_BUCKET="noaa-dev-lambda-layer-${AWS_ACCOUNT_ID}"
export CHATBOT_BUCKET="noaa-chatbot-prod-${AWS_ACCOUNT_ID}"
export GLUE_SCRIPTS_BUCKET="noaa-glue-scripts-${ENV}"

# Athena Database Names
export GOLD_DATABASE="noaa_gold_${ENV}"
export QUERYABLE_DATABASE="noaa_queryable_${ENV}"
export DATALAKE_DATABASE="noaa_datalake_${ENV}"
export FEDERATED_DATABASE="noaa_federated_${ENV}"

# Lambda Function Names
export LAMBDA_ATMOSPHERIC="noaa-ingest-atmospheric-${ENV}"
export LAMBDA_OCEANIC="noaa-ingest-oceanic-${ENV}"
export LAMBDA_BUOY="noaa-ingest-buoy-${ENV}"
export LAMBDA_CLIMATE="noaa-ingest-climate-${ENV}"
export LAMBDA_TERRESTRIAL="noaa-ingest-terrestrial-${ENV}"
export LAMBDA_SPATIAL="noaa-ingest-spatial-${ENV}"
export LAMBDA_AI_QUERY="noaa-ai-query-${ENV}"

# EventBridge Rule Names
export RULE_ATMOSPHERIC="noaa-ingest-atmospheric-schedule-${ENV}"
export RULE_OCEANIC="noaa-ingest-oceanic-schedule-${ENV}"
export RULE_BUOY="noaa-ingest-buoy-schedule-${ENV}"
export RULE_CLIMATE="noaa-ingest-climate-schedule-${ENV}"
export RULE_TERRESTRIAL="noaa-ingest-terrestrial-schedule-${ENV}"
export RULE_SPATIAL="noaa-ingest-spatial-schedule-${ENV}"

# IAM Role Names
export LAMBDA_EXECUTION_ROLE="noaa-lambda-execution-role-${ENV}"
export GLUE_EXECUTION_ROLE="noaa-glue-execution-role-${ENV}"
export STEP_FUNCTIONS_ROLE="noaa-step-functions-role-${ENV}"

# CloudFormation Stack Names
export STACK_NAME="noaa-federated-lake-${ENV}"
export AI_STACK_NAME="noaa-ai-query-${ENV}"
export GLUE_STACK_NAME="noaa-glue-etl-pipeline-${ENV}"
export MONITORING_STACK_NAME="noaa-monitoring-${ENV}"

# ============================================================================
# DATA LAKE PATHS
# ============================================================================

# Bronze Layer (Raw Data)
export BRONZE_PATH="s3://${DATA_LAKE_BUCKET}/bronze/"
export BRONZE_ATMOSPHERIC="${BRONZE_PATH}atmospheric/"
export BRONZE_OCEANIC="${BRONZE_PATH}oceanic/"
export BRONZE_BUOY="${BRONZE_PATH}buoy/"
export BRONZE_CLIMATE="${BRONZE_PATH}climate/"
export BRONZE_TERRESTRIAL="${BRONZE_PATH}terrestrial/"
export BRONZE_SPATIAL="${BRONZE_PATH}spatial/"

# Silver Layer (Processed Data)
export SILVER_PATH="s3://${DATA_LAKE_BUCKET}/silver/"
export SILVER_ATMOSPHERIC="${SILVER_PATH}atmospheric/"
export SILVER_OCEANIC="${SILVER_PATH}oceanic/"
export SILVER_BUOY="${SILVER_PATH}buoy/"
export SILVER_CLIMATE="${SILVER_PATH}climate/"
export SILVER_TERRESTRIAL="${SILVER_PATH}terrestrial/"
export SILVER_SPATIAL="${SILVER_PATH}spatial/"

# Gold Layer (Analytics-Ready Data)
export GOLD_PATH="s3://${DATA_LAKE_BUCKET}/gold/"
export GOLD_ATMOSPHERIC="${GOLD_PATH}atmospheric/"
export GOLD_OCEANIC="${GOLD_PATH}oceanic/"
export GOLD_BUOY="${GOLD_PATH}buoy/"
export GOLD_CLIMATE="${GOLD_PATH}climate/"
export GOLD_TERRESTRIAL="${GOLD_PATH}terrestrial/"
export GOLD_SPATIAL="${GOLD_PATH}spatial/"

# Athena Query Results
export ATHENA_OUTPUT="s3://${ATHENA_RESULTS_BUCKET}/"

# ============================================================================
# BEDROCK / AI CONFIGURATION
# ============================================================================

# Bedrock Model ID for AI queries
export BEDROCK_MODEL="anthropic.claude-3-5-sonnet-20241022-v2:0"
export BEDROCK_REGION="${AWS_REGION}"

# AI Query Configuration
export RELEVANCE_THRESHOLD="0.3"
export MAX_PARALLEL_PONDS="6"
export QUERY_TIMEOUT="300"

# ============================================================================
# INGESTION CONFIGURATION
# ============================================================================

# Ingestion Schedules (EventBridge expressions)
export SCHEDULE_ATMOSPHERIC="rate(15 minutes)"
export SCHEDULE_OCEANIC="rate(15 minutes)"
export SCHEDULE_BUOY="rate(15 minutes)"
export SCHEDULE_CLIMATE="rate(60 minutes)"
export SCHEDULE_TERRESTRIAL="rate(30 minutes)"
export SCHEDULE_SPATIAL="rate(6 hours)"

# Lambda Memory Configurations (MB)
export LAMBDA_MEMORY_INGEST="512"
export LAMBDA_MEMORY_AI="1024"
export LAMBDA_MEMORY_ETL="2048"

# Lambda Timeout Configurations (seconds)
export LAMBDA_TIMEOUT_INGEST="300"
export LAMBDA_TIMEOUT_AI="60"
export LAMBDA_TIMEOUT_ETL="900"

# ============================================================================
# OPERATIONAL CONFIGURATION
# ============================================================================

# Tags for all resources
export TAG_PROJECT="NOAA-Federated-Lake"
export TAG_ENVIRONMENT="${ENVIRONMENT}"
export TAG_COST_CENTER="DataEngineering"
export TAG_MANAGED_BY="Terraform"

# Logging
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export LOG_RETENTION_DAYS="30"

# Monitoring
export ENABLE_XRAY="${ENABLE_XRAY:-false}"
export ENABLE_DETAILED_MONITORING="${ENABLE_DETAILED_MONITORING:-true}"

# Data Retention (days)
export BRONZE_RETENTION="90"
export SILVER_RETENTION="365"
export GOLD_RETENTION="730"

# ============================================================================
# NOAA API CONFIGURATION
# ============================================================================

# NOAA API Endpoints
export NOAA_NWS_API="https://api.weather.gov"
export NOAA_TIDES_API="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
export NOAA_BUOY_API="https://www.ndbc.noaa.gov"
export NOAA_CDO_API="https://www.ncdc.noaa.gov/cdo-web/api/v2"

# API Rate Limiting
export API_RATE_LIMIT="5"
export API_RETRY_ATTEMPTS="3"
export API_BACKOFF_FACTOR="2"

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

# Function to validate environment is properly configured
validate_environment() {
    local errors=0

    echo "Validating NOAA environment configuration..."

    # Check AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        echo "ERROR: AWS CLI is not installed"
        ((errors++))
    fi

    # Verify AWS credentials
    if ! aws sts get-caller-identity --profile "${AWS_PROFILE}" &> /dev/null; then
        echo "ERROR: Cannot authenticate with AWS profile: ${AWS_PROFILE}"
        ((errors++))
    else
        local current_account=$(aws sts get-caller-identity --profile "${AWS_PROFILE}" --query Account --output text)
        if [ "${current_account}" != "${AWS_ACCOUNT_ID}" ]; then
            echo "WARNING: Current account (${current_account}) doesn't match configured account (${AWS_ACCOUNT_ID})"
        fi
    fi

    # Check required environment variables
    local required_vars=("AWS_PROFILE" "AWS_ACCOUNT_ID" "AWS_REGION" "ENVIRONMENT")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "ERROR: Required variable ${var} is not set"
            ((errors++))
        fi
    done

    if [ $errors -eq 0 ]; then
        echo "✓ Environment validation passed"
        return 0
    else
        echo "✗ Environment validation failed with ${errors} error(s)"
        return 1
    fi
}

# Function to display current configuration
show_configuration() {
    echo "============================================================"
    echo "NOAA Federated Data Lake - Environment Configuration"
    echo "============================================================"
    echo ""
    echo "AWS Configuration:"
    echo "  Profile:      ${AWS_PROFILE}"
    echo "  Account ID:   ${AWS_ACCOUNT_ID}"
    echo "  Region:       ${AWS_REGION}"
    echo "  Environment:  ${ENVIRONMENT}"
    echo ""
    echo "S3 Buckets:"
    echo "  Data Lake:    ${DATA_LAKE_BUCKET}"
    echo "  Deployment:   ${DEPLOYMENT_BUCKET}"
    echo "  Athena:       ${ATHENA_RESULTS_BUCKET}"
    echo ""
    echo "Athena Databases:"
    echo "  Gold:         ${GOLD_DATABASE}"
    echo "  Queryable:    ${QUERYABLE_DATABASE}"
    echo ""
    echo "Lambda Functions:"
    echo "  Atmospheric:  ${LAMBDA_ATMOSPHERIC}"
    echo "  Oceanic:      ${LAMBDA_OCEANIC}"
    echo "  Buoy:         ${LAMBDA_BUOY}"
    echo "  Climate:      ${LAMBDA_CLIMATE}"
    echo "  Terrestrial:  ${LAMBDA_TERRESTRIAL}"
    echo "  Spatial:      ${LAMBDA_SPATIAL}"
    echo "  AI Query:     ${LAMBDA_AI_QUERY}"
    echo ""
    echo "============================================================"
}

# ============================================================================
# AUTO-VALIDATION (only if sourced interactively)
# ============================================================================

# Only run validation if explicitly requested or in interactive mode
if [ "${NOAA_VALIDATE_ENV}" = "true" ]; then
    validate_environment
fi

# Uncomment to always show configuration when sourced
# show_configuration

# Export all functions
export -f validate_environment
export -f show_configuration

# Success message
echo "✓ NOAA environment configuration loaded (Account: ${AWS_ACCOUNT_ID}, Profile: ${AWS_PROFILE})"
