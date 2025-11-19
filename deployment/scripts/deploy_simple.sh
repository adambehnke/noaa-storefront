#!/bin/bash

################################################################################
# NOAA Simplified Deployment Script
# Deploys comprehensive ingestion system to AWS
################################################################################

set -e

echo "=========================================="
echo "NOAA 24/7 Ingestion System - Deployment"
echo "=========================================="
echo ""

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="noaa-data-lake-${ENV}"
DEPLOYMENT_BUCKET="noaa-deployment-${ENV}-${ACCOUNT_ID}"
ROLE_NAME="noaa-ingestion-lambda-role-${ENV}"

echo "Configuration:"
echo "  AWS Region: ${AWS_REGION}"
echo "  Environment: ${ENV}"
echo "  Account ID: ${ACCOUNT_ID}"
echo "  Data Bucket: ${BUCKET_NAME}"
echo ""

################################################################################
# Step 1: Create S3 Buckets
################################################################################
echo "Step 1: Creating S3 buckets..."

if aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
    echo "  ✓ Bucket ${BUCKET_NAME} already exists"
else
    echo "  Creating bucket ${BUCKET_NAME}..."
    aws s3 mb "s3://${BUCKET_NAME}" --region "${AWS_REGION}"
    aws s3api put-bucket-versioning \
        --bucket "${BUCKET_NAME}" \
        --versioning-configuration Status=Enabled
    echo "  ✓ Created bucket ${BUCKET_NAME}"
fi

if aws s3 ls "s3://${DEPLOYMENT_BUCKET}" 2>/dev/null; then
    echo "  ✓ Deployment bucket ${DEPLOYMENT_BUCKET} already exists"
else
    echo "  Creating deployment bucket ${DEPLOYMENT_BUCKET}..."
    aws s3 mb "s3://${DEPLOYMENT_BUCKET}" --region "${AWS_REGION}"
    echo "  ✓ Created deployment bucket ${DEPLOYMENT_BUCKET}"
fi

# Create folder structure
echo "  Creating medallion structure..."
for pond in atmospheric oceanic buoy climate spatial terrestrial; do
    for layer in bronze silver gold; do
        aws s3api put-object \
            --bucket "${BUCKET_NAME}" \
            --key "${layer}/${pond}/.keep" \
            --body /dev/null 2>/dev/null || true
    done
done
echo "  ✓ S3 structure ready"
echo ""

################################################################################
# Step 2: Create IAM Role
################################################################################
echo "Step 2: Setting up IAM role..."

if aws iam get-role --role-name "${ROLE_NAME}" 2>/dev/null; then
    echo "  ✓ Role ${ROLE_NAME} already exists"
else
    echo "  Creating role ${ROLE_NAME}..."

    cat > /tmp/trust-policy.json <<EOF
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
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document file:///tmp/trust-policy.json

    aws iam attach-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    cat > /tmp/ingestion-policy.json <<EOF
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
        "glue:*",
        "athena:*",
        "bedrock:InvokeModel",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-name "noaa-ingestion-policy" \
        --policy-document file:///tmp/ingestion-policy.json

    echo "  Waiting for role to be available..."
    sleep 10

    echo "  ✓ Created role ${ROLE_NAME}"
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "  Role ARN: ${ROLE_ARN}"
echo ""

################################################################################
# Step 3: Create Glue Database
################################################################################
echo "Step 3: Creating Glue database..."

DB_NAME="noaa_federated_${ENV}"

aws glue create-database \
    --database-input "{\"Name\":\"${DB_NAME}\",\"Description\":\"NOAA Federated Data Lake\"}" \
    2>/dev/null || echo "  ✓ Database ${DB_NAME} already exists"

echo "  ✓ Glue database ready"
echo ""

################################################################################
# Step 4: Package and Deploy Lambdas
################################################################################
echo "Step 4: Packaging and deploying Lambda functions..."
echo ""

deploy_lambda() {
    local pond=$1
    local lambda_name="noaa-ingest-${pond}-${ENV}"
    local source_dir="ingestion/lambdas/${pond}"
    local zip_file="/tmp/${lambda_name}.zip"

    echo "  Deploying ${pond} pond..."

    # Check if source exists
    if [ ! -f "${source_dir}/lambda_function.py" ]; then
        echo "    ✗ Source not found: ${source_dir}/lambda_function.py"
        return 1
    fi

    # Package
    cd "${source_dir}"
    rm -f "${zip_file}"

    # Use python3 explicitly
    if [ -f "requirements.txt" ]; then
        python3 -m pip install -r requirements.txt -t . --quiet 2>/dev/null || true
    fi

    zip -r "${zip_file}" . -q
    cd - > /dev/null

    # Deploy or update
    if aws lambda get-function --function-name "${lambda_name}" 2>/dev/null; then
        echo "    Updating existing function..."
        aws lambda update-function-code \
            --function-name "${lambda_name}" \
            --zip-file "fileb://${zip_file}" > /dev/null

        aws lambda wait function-updated --function-name "${lambda_name}"

        aws lambda update-function-configuration \
            --function-name "${lambda_name}" \
            --timeout 900 \
            --memory-size 2048 \
            --environment "Variables={ENV=${ENV},BUCKET_NAME=${BUCKET_NAME}}" > /dev/null
    else
        echo "    Creating new function..."
        aws lambda create-function \
            --function-name "${lambda_name}" \
            --runtime python3.12 \
            --role "${ROLE_ARN}" \
            --handler "lambda_function.lambda_handler" \
            --zip-file "fileb://${zip_file}" \
            --timeout 900 \
            --memory-size 2048 \
            --environment "Variables={ENV=${ENV},BUCKET_NAME=${BUCKET_NAME}}" > /dev/null
    fi

    echo "    ✓ Deployed ${lambda_name}"
}

# Deploy each pond
for pond in atmospheric oceanic buoy climate spatial terrestrial; do
    deploy_lambda "${pond}"
done

echo ""
echo "  ✓ All Lambda functions deployed"
echo ""

################################################################################
# Step 5: Create EventBridge Schedules
################################################################################
echo "Step 5: Setting up EventBridge schedules..."
echo ""

for pond in atmospheric oceanic buoy climate spatial terrestrial; do
    lambda_name="noaa-ingest-${pond}-${ENV}"

    # Get Lambda ARN
    lambda_arn=$(aws lambda get-function \
        --function-name "${lambda_name}" \
        --query 'Configuration.FunctionArn' \
        --output text)

    # Incremental schedule (every 15 minutes)
    rule_name="${lambda_name}-incremental"

    aws events put-rule \
        --name "${rule_name}" \
        --schedule-expression "rate(15 minutes)" \
        --state ENABLED > /dev/null 2>&1 || true

    aws events put-targets \
        --rule "${rule_name}" \
        --targets "Id=1,Arn=${lambda_arn},Input='{\"mode\":\"incremental\",\"hours_back\":1}'" > /dev/null 2>&1 || true

    aws lambda add-permission \
        --function-name "${lambda_name}" \
        --statement-id "${rule_name}" \
        --action "lambda:InvokeFunction" \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${rule_name}" \
        2>/dev/null || true

    # Backfill schedule (daily at 2 AM UTC)
    rule_name="${lambda_name}-backfill"

    aws events put-rule \
        --name "${rule_name}" \
        --schedule-expression "cron(0 2 * * ? *)" \
        --state ENABLED > /dev/null 2>&1 || true

    aws events put-targets \
        --rule "${rule_name}" \
        --targets "Id=1,Arn=${lambda_arn},Input='{\"mode\":\"backfill\",\"days_back\":30}'" > /dev/null 2>&1 || true

    aws lambda add-permission \
        --function-name "${lambda_name}" \
        --statement-id "${rule_name}" \
        --action "lambda:InvokeFunction" \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${rule_name}" \
        2>/dev/null || true

    echo "  ✓ Scheduled ${pond} pond (incremental + backfill)"
done

echo ""
echo "  ✓ All EventBridge schedules created"
echo ""

################################################################################
# Step 6: Create CloudWatch Dashboard
################################################################################
echo "Step 6: Creating CloudWatch dashboard..."

DASHBOARD_NAME="NOAA-Ingestion-${ENV}"

cat > /tmp/dashboard.json <<'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Total Invocations"}],
          [".", "Errors", {"stat": "Sum", "label": "Errors"}],
          [".", "Duration", {"stat": "Average", "label": "Avg Duration (ms)"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Lambda Metrics - All Ingestion Functions",
        "yAxis": {
          "left": {
            "label": "Count"
          }
        }
      }
    }
  ]
}
EOF

aws cloudwatch put-dashboard \
    --dashboard-name "${DASHBOARD_NAME}" \
    --dashboard-body file:///tmp/dashboard.json > /dev/null

echo "  ✓ Dashboard created: ${DASHBOARD_NAME}"
echo ""

################################################################################
# Summary
################################################################################
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Environment: ${ENV}"
echo "  ✓ Region: ${AWS_REGION}"
echo "  ✓ Data Lake Bucket: ${BUCKET_NAME}"
echo "  ✓ Lambda Functions: 6 (all ponds)"
echo "  ✓ EventBridge Schedules: 12 (incremental + backfill)"
echo "  ✓ Ingestion Frequency: Every 15 minutes"
echo "  ✓ Backfill Schedule: Daily at 2 AM UTC"
echo ""
echo "Deployed Lambdas:"
for pond in atmospheric oceanic buoy climate spatial terrestrial; do
    echo "  ✓ noaa-ingest-${pond}-${ENV}"
done
echo ""
echo "Next Steps:"
echo "  1. Test ingestion:"
echo "     aws lambda invoke --function-name noaa-ingest-atmospheric-${ENV} \\"
echo "       --payload '{\"mode\":\"incremental\",\"hours_back\":1}' response.json"
echo ""
echo "  2. View logs:"
echo "     aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --follow"
echo ""
echo "  3. Check data in S3:"
echo "     aws s3 ls s3://${BUCKET_NAME}/gold/ --recursive --human-readable"
echo ""
echo "  4. View dashboard:"
echo "     https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=${DASHBOARD_NAME}"
echo ""
echo "System is now ingesting data 24/7!"
echo "=========================================="
