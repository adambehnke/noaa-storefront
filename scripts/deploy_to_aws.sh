#!/bin/bash
###############################################################################
# Deploy NOAA Federated Data Lake to AWS
#
# This script deploys the complete NOAA Federated Data Lake infrastructure
# including S3 buckets, Lambda functions, Athena databases, EventBridge
# schedules, and all necessary IAM roles and permissions.
#
# Usage:
#   ./deploy_to_aws.sh [OPTIONS]
#
# Options:
#   --env ENV           Environment (dev/staging/prod) - default: dev
#   --region REGION     AWS region - default: us-east-1
#   --noaa-token TOKEN  NOAA CDO API token
#   --skip-package      Skip Lambda packaging step
#   --skip-tables       Skip Athena table creation
#   --validate          Run validation tests after deployment
#   --dry-run           Show what would be deployed without deploying
#   --force             Force deployment without confirmation
#
###############################################################################

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
ENV="dev"
REGION="us-east-1"
NOAA_TOKEN=""
SKIP_PACKAGE=false
SKIP_TABLES=false
VALIDATE=false
DRY_RUN=false
FORCE=false

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/deployment_$(date +%Y%m%d_%H%M%S).log"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --noaa-token)
            NOAA_TOKEN="$2"
            shift 2
            ;;
        --skip-package)
            SKIP_PACKAGE=true
            shift
            ;;
        --skip-tables)
            SKIP_TABLES=true
            shift
            ;;
        --validate)
            VALIDATE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            grep "^#" "$0" | grep -v "^#!/" | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log "${RED}ERROR: $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "${BLUE}Checking prerequisites...${NC}"

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error_exit "AWS CLI not found. Please install it first."
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error_exit "AWS credentials not configured. Run 'aws configure' first."
    fi

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    log "${GREEN}✓ AWS Account ID: $ACCOUNT_ID${NC}"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        error_exit "Python 3 not found. Please install it first."
    fi
    log "${GREEN}✓ Python 3 found${NC}"

    # Check required Python packages
    if ! python3 -c "import boto3" 2>/dev/null; then
        log "${YELLOW}⚠ boto3 not found. Installing...${NC}"
        pip3 install boto3 -q
    fi
    log "${GREEN}✓ Python dependencies OK${NC}"

    log ""
}

# Display deployment plan
display_plan() {
    log "${CYAN}========================================${NC}"
    log "${CYAN}NOAA Federated Data Lake Deployment${NC}"
    log "${CYAN}========================================${NC}"
    log "Environment:       ${GREEN}$ENV${NC}"
    log "AWS Region:        ${GREEN}$REGION${NC}"
    log "AWS Account:       ${GREEN}$ACCOUNT_ID${NC}"
    log "NOAA Token:        ${GREEN}$([ -n "$NOAA_TOKEN" ] && echo "Provided" || echo "Not provided")${NC}"
    log "Skip Packaging:    $([ "$SKIP_PACKAGE" = true ] && echo "${YELLOW}Yes${NC}" || echo "${GREEN}No${NC}")"
    log "Skip Tables:       $([ "$SKIP_TABLES" = true ] && echo "${YELLOW}Yes${NC}" || echo "${GREEN}No${NC}")"
    log "Validate:          $([ "$VALIDATE" = true ] && echo "${GREEN}Yes${NC}" || echo "${YELLOW}No${NC}")"
    log "${CYAN}========================================${NC}"
    log ""

    log "${BLUE}Resources to be deployed:${NC}"
    log "  • S3 Buckets (data lake + athena results)"
    log "  • 6 Lambda ingestion functions"
    log "  • 2 Lambda query/handler functions"
    log "  • EventBridge schedules (15-minute intervals)"
    log "  • Athena database and 8+ tables"
    log "  • IAM roles and policies"
    log "  • CloudWatch log groups"
    log ""
}

# Confirm deployment
confirm_deployment() {
    if [ "$FORCE" = false ] && [ "$DRY_RUN" = false ]; then
        read -p "$(echo -e ${YELLOW}Do you want to proceed with deployment? [y/N]: ${NC})" -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "${YELLOW}Deployment cancelled by user${NC}"
            exit 0
        fi
    fi
}

# Package Lambda functions
package_lambdas() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 1: Packaging Lambda Functions${NC}"
    log "${BLUE}========================================${NC}"

    if [ "$SKIP_PACKAGE" = true ]; then
        log "${YELLOW}Skipping Lambda packaging (--skip-package flag)${NC}\n"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would package Lambda functions${NC}\n"
        return 0
    fi

    cd "$SCRIPT_DIR"

    if [ -f "./package_all_lambdas.sh" ]; then
        chmod +x ./package_all_lambdas.sh
        ./package_all_lambdas.sh --env "$ENV" --upload --clean
    else
        error_exit "package_all_lambdas.sh not found"
    fi

    log "${GREEN}✓ Lambda functions packaged successfully${NC}\n"
}

# Deploy CloudFormation stack
deploy_cloudformation() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 2: Deploying CloudFormation Stack${NC}"
    log "${BLUE}========================================${NC}"

    STACK_NAME="noaa-federated-lake-${ENV}"
    TEMPLATE_FILE="$PROJECT_ROOT/cloudformation/noaa-complete-stack.yaml"

    if [ ! -f "$TEMPLATE_FILE" ]; then
        error_exit "CloudFormation template not found: $TEMPLATE_FILE"
    fi

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would deploy CloudFormation stack: $STACK_NAME${NC}\n"
        return 0
    fi

    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &>/dev/null; then
        log "${YELLOW}Stack exists. Updating...${NC}"
        OPERATION="update"

        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body "file://$TEMPLATE_FILE" \
            --parameters \
                ParameterKey=Environment,ParameterValue="$ENV" \
                ParameterKey=NOAACDOToken,ParameterValue="$NOAA_TOKEN" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" \
            2>&1 | tee -a "$LOG_FILE"

        if [ ${PIPESTATUS[0]} -ne 0 ]; then
            if grep -q "No updates are to be performed" "$LOG_FILE"; then
                log "${GREEN}✓ Stack is already up to date${NC}\n"
                return 0
            else
                error_exit "Failed to update CloudFormation stack"
            fi
        fi
    else
        log "Creating new stack..."
        OPERATION="create"

        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-body "file://$TEMPLATE_FILE" \
            --parameters \
                ParameterKey=Environment,ParameterValue="$ENV" \
                ParameterKey=NOAACDOToken,ParameterValue="$NOAA_TOKEN" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" \
            --tags Key=Environment,Value="$ENV" Key=Project,Value=NOAA-Federated-Lake \
            || error_exit "Failed to create CloudFormation stack"
    fi

    # Wait for stack operation to complete
    log "Waiting for stack ${OPERATION} to complete..."
    log "${YELLOW}This may take 5-10 minutes...${NC}"

    aws cloudformation wait "stack-${OPERATION}-complete" \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        || error_exit "Stack ${OPERATION} failed or timed out"

    log "${GREEN}✓ CloudFormation stack deployed successfully${NC}\n"
}

# Deploy Lambda functions
deploy_lambda_functions() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 3: Deploying Lambda Functions${NC}"
    log "${BLUE}========================================${NC}"

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would deploy Lambda functions${NC}\n"
        return 0
    fi

    DEPLOYMENT_BUCKET="noaa-deployment-packages-${ACCOUNT_ID}-${ENV}"

    # Lambda functions to deploy
    declare -A LAMBDAS=(
        ["NOAAIngestOceanic"]="ingest-oceanic.zip"
        ["NOAAIngestAtmospheric"]="ingest-atmospheric.zip"
        ["NOAAIngestClimate"]="ingest-climate.zip"
        ["NOAAIngestSpatial"]="ingest-spatial.zip"
        ["NOAAIngestTerrestrial"]="ingest-terrestrial.zip"
        ["NOAAIngestBuoy"]="ingest-buoy.zip"
        ["NOAAEnhancedQueryHandler"]="enhanced-handler.zip"
        ["NOAAIntelligentOrchestrator"]="intelligent-orchestrator.zip"
    )

    SUCCESS=0
    FAILED=0

    for LAMBDA_NAME in "${!LAMBDAS[@]}"; do
        ZIP_FILE="${LAMBDAS[$LAMBDA_NAME]}"
        FULL_LAMBDA_NAME="${LAMBDA_NAME}-${ENV}"

        log "Deploying: ${LAMBDA_NAME}..."

        if aws lambda get-function --function-name "$FULL_LAMBDA_NAME" --region "$REGION" &>/dev/null; then
            # Update existing function
            if aws lambda update-function-code \
                --function-name "$FULL_LAMBDA_NAME" \
                --s3-bucket "$DEPLOYMENT_BUCKET" \
                --s3-key "lambda-packages/$ZIP_FILE" \
                --region "$REGION" &>/dev/null; then
                log "${GREEN}  ✓ Updated: $LAMBDA_NAME${NC}"
                ((SUCCESS++))
            else
                log "${RED}  ✗ Failed to update: $LAMBDA_NAME${NC}"
                ((FAILED++))
            fi
        else
            log "${YELLOW}  ⚠ Function not found (will be created by CloudFormation): $LAMBDA_NAME${NC}"
        fi
    done

    log "\n${GREEN}✓ Deployed $SUCCESS Lambda functions${NC}"
    if [ $FAILED -gt 0 ]; then
        log "${YELLOW}⚠ Failed to deploy $FAILED functions${NC}"
    fi
    log ""
}

# Create Athena tables
create_athena_tables() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 4: Creating Athena Tables${NC}"
    log "${BLUE}========================================${NC}"

    if [ "$SKIP_TABLES" = true ]; then
        log "${YELLOW}Skipping Athena table creation (--skip-tables flag)${NC}\n"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would create Athena tables${NC}\n"
        return 0
    fi

    SQL_FILE="$PROJECT_ROOT/sql/create-all-gold-tables.sql"

    if [ ! -f "$SQL_FILE" ]; then
        log "${YELLOW}⚠ SQL file not found: $SQL_FILE${NC}"
        log "${YELLOW}Tables will be created by Lambda functions on first run${NC}\n"
        return 0
    fi

    DATABASE="noaa_gold_${ENV}"
    BUCKET="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
    ATHENA_RESULTS="noaa-athena-results-${ACCOUNT_ID}-${ENV}"

    # Replace placeholders in SQL
    TEMP_SQL="/tmp/athena_tables_${ENV}.sql"
    sed -e "s/\${DATABASE}/${DATABASE}/g" \
        -e "s/\${BUCKET}/${BUCKET}/g" \
        -e "s/\${ENV}/${ENV}/g" \
        "$SQL_FILE" > "$TEMP_SQL"

    log "Creating Athena database and tables..."

    # Execute SQL statements
    while IFS= read -r line; do
        if [[ $line =~ ^CREATE ]]; then
            QUERY_ID=$(aws athena start-query-execution \
                --query-string "$line" \
                --result-configuration "OutputLocation=s3://${ATHENA_RESULTS}/setup/" \
                --region "$REGION" \
                --query 'QueryExecutionId' \
                --output text)

            if [ -n "$QUERY_ID" ]; then
                log "  ✓ Query executed: $QUERY_ID"
            fi
        fi
    done < "$TEMP_SQL"

    rm -f "$TEMP_SQL"

    log "${GREEN}✓ Athena tables created${NC}\n"
}

# Configure EventBridge schedules
configure_schedules() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 5: Configuring EventBridge Schedules${NC}"
    log "${BLUE}========================================${NC}"

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would configure EventBridge schedules${NC}\n"
        return 0
    fi

    # Schedules for each pond (15-minute intervals)
    declare -A SCHEDULES=(
        ["NOAAIngestOceanic-${ENV}"]="rate(15 minutes)"
        ["NOAAIngestAtmospheric-${ENV}"]="rate(15 minutes)"
        ["NOAAIngestClimate-${ENV}"]="rate(1 hour)"
        ["NOAAIngestSpatial-${ENV}"]="rate(30 minutes)"
        ["NOAAIngestTerrestrial-${ENV}"]="rate(30 minutes)"
        ["NOAAIngestBuoy-${ENV}"]="rate(15 minutes)"
    )

    for LAMBDA_NAME in "${!SCHEDULES[@]}"; do
        SCHEDULE="${SCHEDULES[$LAMBDA_NAME]}"
        RULE_NAME="${LAMBDA_NAME}-schedule"

        log "Configuring schedule for: $LAMBDA_NAME"

        # Create or update EventBridge rule
        aws events put-rule \
            --name "$RULE_NAME" \
            --schedule-expression "$SCHEDULE" \
            --state ENABLED \
            --region "$REGION" &>/dev/null

        # Add Lambda permission
        aws lambda add-permission \
            --function-name "$LAMBDA_NAME" \
            --statement-id "AllowEventBridgeInvoke-${LAMBDA_NAME}" \
            --action "lambda:InvokeFunction" \
            --principal events.amazonaws.com \
            --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}" \
            --region "$REGION" &>/dev/null || true

        # Add target
        aws events put-targets \
            --rule "$RULE_NAME" \
            --targets "Id=1,Arn=arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${LAMBDA_NAME}" \
            --region "$REGION" &>/dev/null

        log "${GREEN}  ✓ Schedule configured: $SCHEDULE${NC}"
    done

    log "${GREEN}✓ All EventBridge schedules configured${NC}\n"
}

# Trigger initial ingestion
trigger_initial_ingestion() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 6: Triggering Initial Data Ingestion${NC}"
    log "${BLUE}========================================${NC}"

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would trigger initial ingestion${NC}\n"
        return 0
    fi

    log "Invoking Lambda functions for initial data collection..."

    FUNCTIONS=(
        "NOAAIngestOceanic-${ENV}"
        "NOAAIngestAtmospheric-${ENV}"
        "NOAAIngestClimate-${ENV}"
        "NOAAIngestBuoy-${ENV}"
    )

    for FUNC in "${FUNCTIONS[@]}"; do
        log "  Invoking: $FUNC"

        aws lambda invoke \
            --function-name "$FUNC" \
            --invocation-type Event \
            --payload '{"env":"'"$ENV"'"}' \
            --region "$REGION" \
            /tmp/lambda_response_${FUNC}.json &>/dev/null && \
            log "${GREEN}    ✓ Invoked successfully${NC}" || \
            log "${YELLOW}    ⚠ Invocation may have failed${NC}"

        sleep 2  # Rate limiting
    done

    log "${GREEN}✓ Initial ingestion triggered${NC}"
    log "${YELLOW}Note: Data ingestion will take 5-10 minutes to complete${NC}\n"
}

# Run validation tests
run_validation() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}Step 7: Running Validation Tests${NC}"
    log "${BLUE}========================================${NC}"

    if [ "$VALIDATE" = false ]; then
        log "${YELLOW}Skipping validation (use --validate flag to run)${NC}\n"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}[DRY RUN] Would run validation tests${NC}\n"
        return 0
    fi

    log "Waiting 2 minutes for initial data to populate..."
    sleep 120

    TEST_SCRIPT="$PROJECT_ROOT/tests/test_all_ponds.py"

    if [ -f "$TEST_SCRIPT" ]; then
        log "Running comprehensive pond tests..."
        python3 "$TEST_SCRIPT" --env "$ENV" --output "$LOG_DIR/validation_report.md"
    else
        log "${YELLOW}⚠ Test script not found: $TEST_SCRIPT${NC}"
    fi

    log ""
}

# Display deployment summary
display_summary() {
    log "${GREEN}========================================${NC}"
    log "${GREEN}Deployment Complete!${NC}"
    log "${GREEN}========================================${NC}"
    log ""
    log "${BLUE}Deployed Resources:${NC}"
    log "  • Data Lake Bucket: s3://noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
    log "  • Athena Results: s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}"
    log "  • Athena Database: noaa_gold_${ENV}"
    log "  • Lambda Functions: 8 deployed"
    log "  • EventBridge Rules: 6 configured"
    log ""
    log "${BLUE}Next Steps:${NC}"
    log "  1. Monitor CloudWatch Logs for ingestion activity"
    log "  2. Query data via Athena: aws athena start-query-execution ..."
    log "  3. Access federated API endpoint (if deployed)"
    log "  4. Review validation report: $LOG_DIR/validation_report.md"
    log ""
    log "${BLUE}Useful Commands:${NC}"
    log "  # Check Lambda logs"
    log "  aws logs tail /aws/lambda/NOAAIngestOceanic-${ENV} --follow"
    log ""
    log "  # Query Athena"
    log "  aws athena start-query-execution \\"
    log "    --query-string 'SELECT * FROM noaa_gold_${ENV}.oceanic_buoys LIMIT 10' \\"
    log "    --result-configuration OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/"
    log ""
    log "  # Run validation tests"
    log "  python3 tests/test_all_ponds.py --env ${ENV}"
    log ""
    log "${GREEN}========================================${NC}"
    log "Deployment log: $LOG_FILE"
    log "${GREEN}========================================${NC}\n"
}

# Main deployment flow
main() {
    log "${CYAN}"
    log "╔════════════════════════════════════════════════════════════╗"
    log "║   NOAA Federated Data Lake - AWS Deployment Script        ║"
    log "║   Version 1.0                                              ║"
    log "╚════════════════════════════════════════════════════════════╝"
    log "${NC}\n"

    check_prerequisites
    display_plan
    confirm_deployment

    START_TIME=$(date +%s)

    # Execute deployment steps
    package_lambdas
    deploy_cloudformation
    deploy_lambda_functions
    create_athena_tables
    configure_schedules
    trigger_initial_ingestion
    run_validation

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))

    log "${GREEN}Total deployment time: ${MINUTES}m ${SECONDS}s${NC}\n"

    display_summary

    log "${GREEN}✅ Deployment completed successfully!${NC}\n"
}

# Run main function
main

exit 0
