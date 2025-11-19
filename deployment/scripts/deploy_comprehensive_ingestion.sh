#!/bin/bash

################################################################################
# NOAA Comprehensive 24/7 Data Ingestion Deployment Script
# Deploys all ingestion lambdas with medallion architecture
# Sets up continuous ingestion for current and historical data
################################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENT_LOG_DIR="${PROJECT_ROOT}/deployment/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${DEPLOYMENT_LOG_DIR}/deployment_${TIMESTAMP}.log"

# AWS Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

# S3 Configuration
BUCKET_NAME="noaa-data-lake-${ENV}"
DEPLOYMENT_BUCKET="noaa-deployment-${ENV}-${ACCOUNT_ID}"

# Lambda Configuration
LAMBDA_TIMEOUT=900  # 15 minutes
LAMBDA_MEMORY=2048  # 2GB
LAMBDA_RUNTIME="python3.12"

# Data Ponds
DATA_PONDS=("atmospheric" "oceanic" "buoy" "climate" "spatial" "terrestrial")

# Ingestion schedules (cron expressions)
INCREMENTAL_SCHEDULE="rate(15 minutes)"  # Every 15 minutes
BACKFILL_SCHEDULE="cron(0 2 * * ? *)"    # Daily at 2 AM UTC

################################################################################
# Initialization
################################################################################

init_deployment() {
    log_info "Initializing comprehensive ingestion deployment..."

    # Create log directory
    mkdir -p "${DEPLOYMENT_LOG_DIR}"

    # Start logging
    exec > >(tee -a "${LOG_FILE}")
    exec 2>&1

    log_info "Deployment log: ${LOG_FILE}"
    log_info "Project root: ${PROJECT_ROOT}"
    log_info "Environment: ${ENV}"
    log_info "Region: ${AWS_REGION}"
    log_info "Account ID: ${ACCOUNT_ID}"

    # Validate AWS credentials
    if [ -z "${ACCOUNT_ID}" ]; then
        log_error "Unable to get AWS account ID. Please configure AWS credentials."
        exit 1
    fi

    log_success "Initialization complete"
}

################################################################################
# S3 Setup
################################################################################

setup_s3_buckets() {
    log_info "Setting up S3 buckets and medallion structure..."

    # Create main data lake bucket
    if aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
        log_warning "Bucket ${BUCKET_NAME} already exists"
    else
        log_info "Creating bucket ${BUCKET_NAME}..."
        aws s3 mb "s3://${BUCKET_NAME}" --region "${AWS_REGION}"

        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "${BUCKET_NAME}" \
            --versioning-configuration Status=Enabled

        log_success "Created bucket ${BUCKET_NAME}"
    fi

    # Create deployment bucket
    if aws s3 ls "s3://${DEPLOYMENT_BUCKET}" 2>/dev/null; then
        log_warning "Deployment bucket ${DEPLOYMENT_BUCKET} already exists"
    else
        log_info "Creating deployment bucket ${DEPLOYMENT_BUCKET}..."
        aws s3 mb "s3://${DEPLOYMENT_BUCKET}" --region "${AWS_REGION}"
        log_success "Created deployment bucket ${DEPLOYMENT_BUCKET}"
    fi

    # Create medallion structure for each pond
    for pond in "${DATA_PONDS[@]}"; do
        log_info "Creating medallion structure for ${pond} pond..."

        for layer in bronze silver gold; do
            aws s3api put-object \
                --bucket "${BUCKET_NAME}" \
                --key "${layer}/${pond}/.keep" \
                --body /dev/null 2>/dev/null || true
        done
    done

    log_success "S3 structure created"
}

################################################################################
# IAM Roles and Policies
################################################################################

create_lambda_execution_role() {
    local role_name="noaa-ingestion-lambda-role-${ENV}"

    log_info "Creating IAM role: ${role_name}..."

    # Check if role exists
    if aws iam get-role --role-name "${role_name}" 2>/dev/null; then
        log_warning "Role ${role_name} already exists"
        echo "${role_name}"
        return
    fi

    # Create trust policy
    local trust_policy=$(cat <<EOF
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
)

    # Create role
    aws iam create-role \
        --role-name "${role_name}" \
        --assume-role-policy-document "${trust_policy}" \
        --description "Execution role for NOAA ingestion lambdas"

    # Attach managed policies
    aws iam attach-role-policy \
        --role-name "${role_name}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    # Create and attach custom policy
    local policy_document=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}/*",
        "arn:aws:s3:::${BUCKET_NAME}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetTable",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:GetPartitions",
        "glue:CreatePartition",
        "glue:BatchCreatePartition"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    }
  ]
}
EOF
)

    local policy_name="noaa-ingestion-policy-${ENV}"
    aws iam put-role-policy \
        --role-name "${role_name}" \
        --policy-name "${policy_name}" \
        --policy-document "${policy_document}"

    # Wait for role to be available
    sleep 10

    log_success "Created IAM role: ${role_name}"
    echo "${role_name}"
}

################################################################################
# Lambda Deployment Functions
################################################################################

package_lambda() {
    local lambda_name=$1
    local source_dir="${PROJECT_ROOT}/ingestion/lambdas/${lambda_name}"
    local package_dir="/tmp/lambda_package_${lambda_name}_${TIMESTAMP}"
    local zip_file="${DEPLOYMENT_LOG_DIR}/${lambda_name}_${TIMESTAMP}.zip"

    log_info "Packaging ${lambda_name} lambda..."

    # Create package directory
    mkdir -p "${package_dir}"

    # Copy lambda code
    cp -r "${source_dir}"/* "${package_dir}/"

    # Install dependencies if requirements.txt exists
    if [ -f "${package_dir}/requirements.txt" ]; then
        log_info "Installing dependencies for ${lambda_name}..."
        pip install -r "${package_dir}/requirements.txt" -t "${package_dir}" --quiet
    fi

    # Create zip file
    cd "${package_dir}"
    zip -r "${zip_file}" . -q
    cd - > /dev/null

    # Cleanup
    rm -rf "${package_dir}"

    log_success "Packaged ${lambda_name}: ${zip_file}"
    echo "${zip_file}"
}

deploy_lambda() {
    local pond_name=$1
    local role_arn=$2
    local lambda_name="noaa-ingest-${pond_name}-${ENV}"

    log_info "Deploying lambda: ${lambda_name}..."

    # Package lambda
    local zip_file=$(package_lambda "${pond_name}")

    # Check if lambda exists
    if aws lambda get-function --function-name "${lambda_name}" 2>/dev/null; then
        log_info "Updating existing lambda: ${lambda_name}..."

        # Update code
        aws lambda update-function-code \
            --function-name "${lambda_name}" \
            --zip-file "fileb://${zip_file}" \
            > /dev/null

        # Wait for update
        aws lambda wait function-updated --function-name "${lambda_name}"

        # Update configuration
        aws lambda update-function-configuration \
            --function-name "${lambda_name}" \
            --timeout "${LAMBDA_TIMEOUT}" \
            --memory-size "${LAMBDA_MEMORY}" \
            --environment "Variables={ENV=${ENV},BUCKET_NAME=${BUCKET_NAME}}" \
            > /dev/null

    else
        log_info "Creating new lambda: ${lambda_name}..."

        # Create lambda
        aws lambda create-function \
            --function-name "${lambda_name}" \
            --runtime "${LAMBDA_RUNTIME}" \
            --role "${role_arn}" \
            --handler "lambda_function.lambda_handler" \
            --zip-file "fileb://${zip_file}" \
            --timeout "${LAMBDA_TIMEOUT}" \
            --memory-size "${LAMBDA_MEMORY}" \
            --environment "Variables={ENV=${ENV},BUCKET_NAME=${BUCKET_NAME}}" \
            --description "NOAA ${pond_name} data ingestion with medallion architecture" \
            > /dev/null
    fi

    log_success "Deployed lambda: ${lambda_name}"
    echo "${lambda_name}"
}

################################################################################
# EventBridge Schedules
################################################################################

create_eventbridge_rule() {
    local lambda_name=$1
    local schedule=$2
    local rule_type=$3
    local rule_name="${lambda_name}-${rule_type}"

    log_info "Creating EventBridge rule: ${rule_name}..."

    # Create rule
    aws events put-rule \
        --name "${rule_name}" \
        --schedule-expression "${schedule}" \
        --state ENABLED \
        --description "NOAA ${rule_type} ingestion schedule" \
        > /dev/null

    # Get lambda ARN
    local lambda_arn=$(aws lambda get-function \
        --function-name "${lambda_name}" \
        --query 'Configuration.FunctionArn' \
        --output text)

    # Create input for lambda based on type
    local input
    if [ "${rule_type}" == "incremental" ]; then
        input='{"mode":"incremental","hours_back":1}'
    else
        input='{"mode":"backfill","days_back":30}'
    fi

    # Add target
    aws events put-targets \
        --rule "${rule_name}" \
        --targets "Id=1,Arn=${lambda_arn},Input='${input}'" \
        > /dev/null

    # Add permission for EventBridge to invoke lambda
    aws lambda add-permission \
        --function-name "${lambda_name}" \
        --statement-id "${rule_name}" \
        --action "lambda:InvokeFunction" \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${rule_name}" \
        2>/dev/null || true

    log_success "Created EventBridge rule: ${rule_name}"
}

################################################################################
# Glue Database and Tables
################################################################################

create_glue_database() {
    local db_name="noaa_federated_${ENV}"

    log_info "Creating Glue database: ${db_name}..."

    aws glue create-database \
        --database-input "{\"Name\":\"${db_name}\",\"Description\":\"NOAA Federated Data Lake\"}" \
        2>/dev/null || log_warning "Database ${db_name} already exists"

    log_success "Glue database ready: ${db_name}"
}

create_glue_tables() {
    local db_name="noaa_federated_${ENV}"

    log_info "Creating Glue tables for all ponds..."

    for pond in "${DATA_PONDS[@]}"; do
        for layer in bronze silver gold; do
            local table_name="${pond}_${layer}"

            log_info "Creating table: ${table_name}..."

            # Create table definition (simplified - should be customized per pond)
            local table_input=$(cat <<EOF
{
  "Name": "${table_name}",
  "StorageDescriptor": {
    "Columns": [
      {"Name": "record_id", "Type": "string"},
      {"Name": "timestamp", "Type": "string"},
      {"Name": "ingestion_timestamp", "Type": "string"},
      {"Name": "data_source", "Type": "string"}
    ],
    "Location": "s3://${BUCKET_NAME}/${layer}/${pond}/",
    "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
    "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
    "SerdeInfo": {
      "SerializationLibrary": "org.openx.data.jsonserde.JsonSerDe"
    }
  },
  "PartitionKeys": [
    {"Name": "year", "Type": "int"},
    {"Name": "month", "Type": "int"},
    {"Name": "day", "Type": "int"}
  ],
  "TableType": "EXTERNAL_TABLE"
}
EOF
)

            aws glue create-table \
                --database-name "${db_name}" \
                --table-input "${table_input}" \
                2>/dev/null || log_warning "Table ${table_name} already exists"
        done
    done

    log_success "Glue tables created"
}

################################################################################
# AI Matching System
################################################################################

deploy_ai_matching_lambda() {
    local role_arn=$1
    local lambda_name="noaa-ai-data-matcher-${ENV}"

    log_info "Deploying AI data matching lambda..."

    # Create Lambda code inline (simplified version)
    local code_dir="/tmp/ai_matcher_${TIMESTAMP}"
    mkdir -p "${code_dir}"

    cat > "${code_dir}/lambda_function.py" <<'EOFPYTHON'
"""
AI-powered data matching system
Matches and relates data across ponds using Bedrock
"""
import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock = boto3.client('bedrock-runtime')

def lambda_handler(event, context):
    """Match related data across ponds"""
    try:
        source_pond = event.get('source_pond')
        source_data = event.get('source_data')

        # Use Bedrock to find relationships
        prompt = f"""Analyze this {source_pond} data and identify which other NOAA data ponds
(atmospheric, oceanic, buoy, climate, spatial, terrestrial) would have related information.
For each related pond, explain the relationship.

Data: {json.dumps(source_data)}

Return JSON with: {{"related_ponds": [{{"pond": "name", "relationship": "description", "relevance": 0-1}}]}}"""

        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}]
            })
        )

        result = json.loads(response['body'].read())
        content = result['content'][0]['text']

        return {
            'statusCode': 200,
            'body': json.dumps({'matches': content})
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
EOFPYTHON

    # Package
    cd "${code_dir}"
    local zip_file="${DEPLOYMENT_LOG_DIR}/ai_matcher_${TIMESTAMP}.zip"
    zip -r "${zip_file}" . -q
    cd - > /dev/null

    # Deploy
    if aws lambda get-function --function-name "${lambda_name}" 2>/dev/null; then
        aws lambda update-function-code \
            --function-name "${lambda_name}" \
            --zip-file "fileb://${zip_file}" \
            > /dev/null
    else
        aws lambda create-function \
            --function-name "${lambda_name}" \
            --runtime "python3.12" \
            --role "${role_arn}" \
            --handler "lambda_function.lambda_handler" \
            --zip-file "fileb://${zip_file}" \
            --timeout 60 \
            --memory-size 512 \
            --environment "Variables={ENV=${ENV}}" \
            > /dev/null
    fi

    rm -rf "${code_dir}"

    log_success "Deployed AI matching lambda: ${lambda_name}"
}

################################################################################
# Monitoring and Alerts
################################################################################

setup_cloudwatch_dashboard() {
    local dashboard_name="NOAA-Ingestion-${ENV}"

    log_info "Creating CloudWatch dashboard: ${dashboard_name}..."

    local dashboard_body=$(cat <<'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
          [".", "Errors", {"stat": "Sum"}],
          [".", "Duration", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Lambda Metrics"
      }
    }
  ]
}
EOF
)

    aws cloudwatch put-dashboard \
        --dashboard-name "${dashboard_name}" \
        --dashboard-body "${dashboard_body}" \
        > /dev/null

    log_success "Created CloudWatch dashboard"
}

create_sns_alerts() {
    local topic_name="noaa-ingestion-alerts-${ENV}"

    log_info "Creating SNS topic for alerts: ${topic_name}..."

    local topic_arn=$(aws sns create-topic \
        --name "${topic_name}" \
        --query 'TopicArn' \
        --output text 2>/dev/null || \
        aws sns list-topics \
        --query "Topics[?contains(TopicArn, '${topic_name}')].TopicArn" \
        --output text)

    log_success "SNS topic ready: ${topic_arn}"
    echo "${topic_arn}"
}

################################################################################
# Main Deployment
################################################################################

main() {
    log_info "=========================================="
    log_info "NOAA 24/7 Comprehensive Ingestion Deployment"
    log_info "=========================================="
    echo

    # Initialize
    init_deployment
    echo

    # Setup S3
    setup_s3_buckets
    echo

    # Create IAM role
    log_info "Setting up IAM roles..."
    local role_name=$(create_lambda_execution_role)
    local role_arn="arn:aws:iam::${ACCOUNT_ID}:role/${role_name}"
    log_success "IAM role ARN: ${role_arn}"
    echo

    # Create Glue database and tables
    create_glue_database
    create_glue_tables
    echo

    # Deploy lambdas for each pond
    log_info "Deploying ingestion lambdas..."
    for pond in "${DATA_PONDS[@]}"; do
        log_info "----------------------------------------"
        local lambda_name=$(deploy_lambda "${pond}" "${role_arn}")

        # Create incremental schedule (every 15 minutes)
        create_eventbridge_rule "${lambda_name}" "${INCREMENTAL_SCHEDULE}" "incremental"

        # Create backfill schedule (daily)
        create_eventbridge_rule "${lambda_name}" "${BACKFILL_SCHEDULE}" "backfill"

        log_success "Deployed ${pond} pond with 24/7 ingestion"
    done
    echo

    # Deploy AI matching system
    deploy_ai_matching_lambda "${role_arn}"
    echo

    # Setup monitoring
    setup_cloudwatch_dashboard
    local sns_arn=$(create_sns_alerts)
    echo

    # Summary
    log_info "=========================================="
    log_success "DEPLOYMENT COMPLETE!"
    log_info "=========================================="
    echo
    log_info "Summary:"
    log_info "  - Environment: ${ENV}"
    log_info "  - Region: ${AWS_REGION}"
    log_info "  - Data Lake Bucket: ${BUCKET_NAME}"
    log_info "  - Ponds Deployed: ${#DATA_PONDS[@]}"
    log_info "  - Incremental Schedule: Every 15 minutes"
    log_info "  - Backfill Schedule: Daily at 2 AM UTC"
    log_info "  - Medallion Layers: Bronze -> Silver -> Gold"
    log_info "  - AI Matching: Enabled"
    echo
    log_info "Deployed Lambdas:"
    for pond in "${DATA_PONDS[@]}"; do
        log_info "  ✓ noaa-ingest-${pond}-${ENV}"
    done
    log_info "  ✓ noaa-ai-data-matcher-${ENV}"
    echo
    log_info "Next Steps:"
    log_info "  1. Monitor ingestion: aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --follow"
    log_info "  2. Check S3 data: aws s3 ls s3://${BUCKET_NAME}/gold/ --recursive --human-readable"
    log_info "  3. Query with Athena: SELECT * FROM noaa_federated_${ENV}.atmospheric_gold LIMIT 10"
    log_info "  4. View dashboard: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-Ingestion-${ENV}"
    echo
    log_info "Log file: ${LOG_FILE}"
    log_success "System is now ingesting data 24/7!"
}

# Run main deployment
main "$@"
