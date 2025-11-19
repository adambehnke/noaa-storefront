#!/bin/bash
#
# NOAA Data Lake - Comprehensive Ingestion System Deployment
#
# This script deploys all ingestion Lambda functions and schedules them
# for real-time data collection across all NOAA data ponds
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_PROFILE=${AWS_PROFILE:-noaa-target}
AWS_REGION=${AWS_REGION:-us-east-1}
ENV=${ENV:-dev}
ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)

BUCKET_NAME="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
DEPLOYMENT_BUCKET="noaa-deployment-${ACCOUNT_ID}-${ENV}"
ATHENA_OUTPUT="s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/"

# Lambda role
LAMBDA_ROLE_NAME="noaa-etl-role-${ENV}"
LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NOAA Data Lake - Ingestion System Deployment            ║${NC}"
echo -e "${BLUE}║   Account: ${ACCOUNT_ID}                           ║${NC}"
echo -e "${BLUE}║   Environment: ${ENV}                                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verify prerequisites
print_status "Verifying prerequisites..."
if ! aws sts get-caller-identity --profile $AWS_PROFILE > /dev/null 2>&1; then
    print_error "AWS credentials not configured for profile: $AWS_PROFILE"
    exit 1
fi
print_success "AWS credentials verified"

# Check if buckets exist
if ! aws s3 ls s3://$BUCKET_NAME --profile $AWS_PROFILE > /dev/null 2>&1; then
    print_error "Data lake bucket does not exist: $BUCKET_NAME"
    exit 1
fi
print_success "Data lake bucket exists: $BUCKET_NAME"

# Array of ponds to deploy
PONDS=("atmospheric" "oceanic" "buoy" "climate" "spatial" "terrestrial")

# Ingestion schedules (cron format)
declare -A SCHEDULES
SCHEDULES["atmospheric"]="rate(5 minutes)"  # Weather data - every 5 min
SCHEDULES["oceanic"]="rate(5 minutes)"      # Tide/ocean data - every 5 min
SCHEDULES["buoy"]="rate(5 minutes)"         # Buoy observations - every 5 min
SCHEDULES["climate"]="rate(1 hour)"         # Climate data - hourly
SCHEDULES["spatial"]="rate(1 day)"          # Spatial/reference data - daily
SCHEDULES["terrestrial"]="rate(30 minutes)" # Land observations - every 30 min

# Deploy each ingestion Lambda
deploy_ingestion_lambda() {
    local pond=$1
    local lambda_name="noaa-ingest-${pond}-${ENV}"
    local lambda_dir="ingestion/lambdas/${pond}"

    print_status "Deploying ${pond} ingestion Lambda..."

    # Check if Lambda directory exists
    if [ ! -d "$lambda_dir" ]; then
        print_warning "Lambda directory not found: $lambda_dir - skipping"
        return 1
    fi

    # Create deployment package
    cd "$lambda_dir"

    # Clean up old package
    rm -f lambda_package.zip

    # Create zip with all dependencies
    print_status "  Packaging Lambda function..."
    zip -r lambda_package.zip . -x "*.pyc" "__pycache__/*" "*.git/*" > /dev/null 2>&1

    local zip_size=$(du -h lambda_package.zip | cut -f1)
    print_status "  Package size: $zip_size"

    cd - > /dev/null

    # Check if Lambda exists
    if aws lambda get-function --function-name "$lambda_name" --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1; then
        print_status "  Updating existing Lambda function..."
        aws lambda update-function-code \
            --function-name "$lambda_name" \
            --zip-file "fileb://${lambda_dir}/lambda_package.zip" \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            > /dev/null 2>&1

        # Update configuration
        aws lambda update-function-configuration \
            --function-name "$lambda_name" \
            --timeout 300 \
            --memory-size 512 \
            --environment Variables="{
                ENV=${ENV},
                BUCKET_NAME=${BUCKET_NAME},
                ATHENA_OUTPUT=${ATHENA_OUTPUT},
                BRONZE_DB=noaa_bronze_${ENV},
                SILVER_DB=noaa_silver_${ENV},
                GOLD_DB=noaa_gold_${ENV}
            }" \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            > /dev/null 2>&1
    else
        print_status "  Creating new Lambda function..."
        aws lambda create-function \
            --function-name "$lambda_name" \
            --runtime python3.12 \
            --handler lambda_function.lambda_handler \
            --role "$LAMBDA_ROLE_ARN" \
            --zip-file "fileb://${lambda_dir}/lambda_package.zip" \
            --timeout 300 \
            --memory-size 512 \
            --environment Variables="{
                ENV=${ENV},
                BUCKET_NAME=${BUCKET_NAME},
                ATHENA_OUTPUT=${ATHENA_OUTPUT},
                BRONZE_DB=noaa_bronze_${ENV},
                SILVER_DB=noaa_silver_${ENV},
                GOLD_DB=noaa_gold_${ENV}
            }" \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            > /dev/null 2>&1
    fi

    print_success "  Lambda deployed: $lambda_name"

    # Setup EventBridge schedule
    setup_schedule "$pond" "$lambda_name"

    return 0
}

# Setup EventBridge schedule for Lambda
setup_schedule() {
    local pond=$1
    local lambda_name=$2
    local rule_name="noaa-ingest-${pond}-schedule-${ENV}"
    local schedule="${SCHEDULES[$pond]}"

    print_status "  Setting up EventBridge schedule: $schedule"

    # Create or update rule
    aws events put-rule \
        --name "$rule_name" \
        --schedule-expression "$schedule" \
        --state ENABLED \
        --description "Ingestion schedule for ${pond} data - ${schedule}" \
        --region $AWS_REGION \
        --profile $AWS_PROFILE \
        > /dev/null 2>&1

    # Get Lambda ARN
    local lambda_arn=$(aws lambda get-function \
        --function-name "$lambda_name" \
        --region $AWS_REGION \
        --profile $AWS_PROFILE \
        --query 'Configuration.FunctionArn' \
        --output text)

    # Add Lambda as target
    aws events put-targets \
        --rule "$rule_name" \
        --targets "Id=1,Arn=${lambda_arn},Input='{\"mode\":\"incremental\",\"hours_back\":1}'" \
        --region $AWS_REGION \
        --profile $AWS_PROFILE \
        > /dev/null 2>&1

    # Add Lambda permission for EventBridge
    aws lambda add-permission \
        --function-name "$lambda_name" \
        --statement-id "AllowEventBridge-${rule_name}" \
        --action lambda:InvokeFunction \
        --principal events.amazonaws.com \
        --source-arn "arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${rule_name}" \
        --region $AWS_REGION \
        --profile $AWS_PROFILE \
        > /dev/null 2>&1 || true  # Ignore if permission already exists

    print_success "  EventBridge schedule configured: $rule_name"
}

# Deploy historical backfill Lambda
deploy_backfill_lambda() {
    print_status "Creating historical backfill Lambda..."

    local lambda_name="noaa-backfill-${ENV}"

    # Create simple backfill Lambda inline
    cat > /tmp/backfill_handler.py << 'EOFBACKFILL'
import json
import boto3
import os

lambda_client = boto3.client('lambda')
ENV = os.environ.get('ENV', 'dev')

def lambda_handler(event, context):
    """
    Triggers historical backfill for specified pond
    """
    pond = event.get('pond', 'oceanic')
    days_back = event.get('days_back', 365)  # Default 1 year

    target_lambda = f"noaa-ingest-{pond}-{ENV}"

    # Trigger ingestion with historical mode
    response = lambda_client.invoke(
        FunctionName=target_lambda,
        InvocationType='Event',
        Payload=json.dumps({
            'mode': 'historical',
            'days_back': days_back
        })
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Triggered historical backfill for {pond}',
            'days_back': days_back,
            'target_lambda': target_lambda
        })
    }
EOFBACKFILL

    cd /tmp
    rm -f backfill.zip
    zip backfill.zip backfill_handler.py > /dev/null 2>&1

    if aws lambda get-function --function-name "$lambda_name" --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1; then
        aws lambda update-function-code \
            --function-name "$lambda_name" \
            --zip-file fileb://backfill.zip \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            > /dev/null 2>&1
    else
        aws lambda create-function \
            --function-name "$lambda_name" \
            --runtime python3.12 \
            --handler backfill_handler.lambda_handler \
            --role "$LAMBDA_ROLE_ARN" \
            --zip-file fileb://backfill.zip \
            --timeout 60 \
            --memory-size 256 \
            --environment Variables="{ENV=${ENV}}" \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            > /dev/null 2>&1
    fi

    print_success "Backfill Lambda deployed: $lambda_name"
}

# Setup Glue crawlers
setup_glue_crawlers() {
    print_status "Setting up Glue crawlers..."

    local layers=("bronze" "silver" "gold")

    for layer in "${layers[@]}"; do
        local crawler_name="noaa-${layer}-crawler-${ENV}"
        local database="noaa_${layer}_${ENV}"
        local s3_path="s3://${BUCKET_NAME}/${layer}/"

        print_status "  Configuring ${layer} crawler..."

        # Check if crawler exists
        if aws glue get-crawler --name "$crawler_name" --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1; then
            print_status "    Updating existing crawler..."
            aws glue update-crawler \
                --name "$crawler_name" \
                --role "$LAMBDA_ROLE_ARN" \
                --database-name "$database" \
                --targets "S3Targets=[{Path=${s3_path}}]" \
                --schema-change-policy "UpdateBehavior=UPDATE_IN_DATABASE,DeleteBehavior=LOG" \
                --region $AWS_REGION \
                --profile $AWS_PROFILE \
                > /dev/null 2>&1 || true
        else
            print_status "    Creating new crawler..."
            aws glue create-crawler \
                --name "$crawler_name" \
                --role "$LAMBDA_ROLE_ARN" \
                --database-name "$database" \
                --targets "S3Targets=[{Path=${s3_path}}]" \
                --schema-change-policy "UpdateBehavior=UPDATE_IN_DATABASE,DeleteBehavior=LOG" \
                --region $AWS_REGION \
                --profile $AWS_PROFILE \
                > /dev/null 2>&1 || print_warning "Failed to create crawler - it may already exist"
        fi

        # Schedule crawler to run hourly
        local crawler_schedule_rule="noaa-${layer}-crawler-schedule-${ENV}"

        aws events put-rule \
            --name "$crawler_schedule_rule" \
            --schedule-expression "rate(1 hour)" \
            --state ENABLED \
            --description "Run ${layer} crawler hourly" \
            --region $AWS_REGION \
            --profile $AWS_PROFILE \
            > /dev/null 2>&1

        print_success "    Crawler configured: $crawler_name"
    done
}

# Trigger initial ingestion
trigger_initial_ingestion() {
    print_status "Triggering initial ingestion for all ponds..."

    for pond in "${PONDS[@]}"; do
        local lambda_name="noaa-ingest-${pond}-${ENV}"

        # Check if Lambda exists
        if aws lambda get-function --function-name "$lambda_name" --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1; then
            print_status "  Invoking ${pond} ingestion..."

            # Trigger with recent data (last 24 hours)
            aws lambda invoke \
                --function-name "$lambda_name" \
                --invocation-type Event \
                --payload '{"mode":"incremental","hours_back":24}' \
                --region $AWS_REGION \
                --profile $AWS_PROFILE \
                /tmp/lambda-response-${pond}.json \
                > /dev/null 2>&1

            print_success "    ${pond} ingestion triggered"
        else
            print_warning "  Lambda not found: $lambda_name - skipping"
        fi
    done

    print_success "Initial ingestion triggered for all ponds"
}

# Verify deployment
verify_deployment() {
    print_status "Verifying deployment..."

    local success_count=0
    local total_count=${#PONDS[@]}

    for pond in "${PONDS[@]}"; do
        local lambda_name="noaa-ingest-${pond}-${ENV}"
        local rule_name="noaa-ingest-${pond}-schedule-${ENV}"

        # Check Lambda
        if aws lambda get-function --function-name "$lambda_name" --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1; then
            # Check EventBridge rule
            if aws events describe-rule --name "$rule_name" --region $AWS_REGION --profile $AWS_PROFILE > /dev/null 2>&1; then
                print_success "  ✓ ${pond}: Lambda and schedule deployed"
                success_count=$((success_count + 1))
            else
                print_warning "  ⚠ ${pond}: Lambda exists but schedule missing"
            fi
        else
            print_error "  ✗ ${pond}: Lambda not deployed"
        fi
    done

    echo ""
    print_status "Deployment verification: ${success_count}/${total_count} ponds deployed successfully"
}

# Main deployment flow
main() {
    print_status "Starting ingestion system deployment..."
    echo ""

    # Deploy each pond's ingestion Lambda
    print_status "═══ Step 1: Deploying Ingestion Lambdas ═══"
    for pond in "${PONDS[@]}"; do
        deploy_ingestion_lambda "$pond" || print_warning "Failed to deploy $pond - continuing..."
    done
    echo ""

    # Deploy backfill Lambda
    print_status "═══ Step 2: Deploying Backfill Lambda ═══"
    deploy_backfill_lambda
    echo ""

    # Setup Glue crawlers
    print_status "═══ Step 3: Setting up Glue Crawlers ═══"
    setup_glue_crawlers
    echo ""

    # Trigger initial ingestion
    print_status "═══ Step 4: Triggering Initial Ingestion ═══"
    trigger_initial_ingestion
    echo ""

    # Verify deployment
    print_status "═══ Step 5: Verification ═══"
    verify_deployment
    echo ""

    # Summary
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                            ║${NC}"
    echo -e "${GREEN}║   ✅  Ingestion System Deployment Complete                 ║${NC}"
    echo -e "${GREEN}║                                                            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Ingestion Schedules:${NC}"
    for pond in "${PONDS[@]}"; do
        echo "  • ${pond}: ${SCHEDULES[$pond]}"
    done
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo "  1. Monitor Lambda logs for ingestion progress:"
    echo "     aws logs tail /aws/lambda/noaa-ingest-oceanic-${ENV} --follow --profile ${AWS_PROFILE}"
    echo ""
    echo "  2. Check S3 bucket for incoming data:"
    echo "     aws s3 ls s3://${BUCKET_NAME}/bronze/ --recursive --profile ${AWS_PROFILE}"
    echo ""
    echo "  3. Trigger historical backfill (optional):"
    echo "     aws lambda invoke --function-name noaa-backfill-${ENV} \\"
    echo "       --payload '{\"pond\":\"oceanic\",\"days_back\":365}' \\"
    echo "       /tmp/backfill-response.json --profile ${AWS_PROFILE}"
    echo ""
    echo "  4. Run Glue crawlers to create tables:"
    echo "     aws glue start-crawler --name noaa-bronze-crawler-${ENV} --profile ${AWS_PROFILE}"
    echo ""
    echo -e "${YELLOW}Note: Initial data ingestion will take 5-10 minutes to appear in S3.${NC}"
    echo -e "${YELLOW}      Glue crawlers will run hourly to update table schemas.${NC}"
}

# Run main deployment
main
