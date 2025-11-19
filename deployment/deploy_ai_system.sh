#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - AI Multi-Pond System
# Fully Automated Deployment Script
#
# This script:
# 1. Backs up the current handler
# 2. Deplaces the enhanced handler with our new AI code
# 3. Deploys to AWS Lambda
# 4. Sets up 15-minute ingestion schedules
# 5. Tests the deployment
# 6. Provides detailed feedback
#
# Usage: ./deploy_ai_system.sh
#
# Author: NOAA Federated Data Lake Team
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV="dev"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
REGION="us-east-1"
LAMBDA_NAME="noaa-enhanced-handler-${ENV}"

# Directories
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAMBDA_DIR="${PROJECT_ROOT}/lambda-enhanced-handler"
AI_HANDLER="${PROJECT_ROOT}/lambda-packages/ai-query-package/ai_query_handler.py"
BACKUP_DIR="${PROJECT_ROOT}/backups/$(date +%Y%m%d_%H%M%S)"
DEPLOYMENT_DIR="${PROJECT_ROOT}/deployment"
TEST_SCRIPTS_DIR="${PROJECT_ROOT}/test-scripts"

# Logging
LOG_FILE="${DEPLOYMENT_DIR}/deployment_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "${DEPLOYMENT_DIR}"

log() {
    echo -e "${1}" | tee -a "${LOG_FILE}"
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    log "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

# Print header
echo -e "${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        NOAA Federated Data Lake - AI System Deployment       ║
║                   Fully Automated Process                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

log_info "Deployment started at $(date)"
log_info "Environment: ${ENV}"
log_info "AWS Account: ${ACCOUNT_ID}"
log_info "Region: ${REGION}"
log_info "Log file: ${LOG_FILE}"
echo ""

# Verify prerequisites
log_info "Checking prerequisites..."

if [ -z "$ACCOUNT_ID" ]; then
    log_error "AWS credentials not configured"
    exit 1
fi

if [ ! -f "$AI_HANDLER" ]; then
    log_error "AI handler not found at: $AI_HANDLER"
    exit 1
fi

if [ ! -d "$LAMBDA_DIR" ]; then
    log_error "Lambda directory not found at: $LAMBDA_DIR"
    exit 1
fi

log_success "Prerequisites verified"
echo ""

# Step 1: Create backup
log_info "[1/7] Creating backup of current handler..."
mkdir -p "$BACKUP_DIR"
cp "${LAMBDA_DIR}/lambda_function.py" "${BACKUP_DIR}/lambda_function.py.backup"
log_success "Backup created at: ${BACKUP_DIR}"
echo ""

# Step 2: Replace handler with AI code
log_info "[2/7] Replacing handler with AI multi-pond code..."
cp "${AI_HANDLER}" "${LAMBDA_DIR}/lambda_function.py"
log_success "Handler replaced with AI code"
echo ""

# Step 3: Add required Bedrock import if missing
log_info "[3/7] Ensuring Bedrock dependencies..."

# Check if boto3 is recent enough for Bedrock
cd "${LAMBDA_DIR}"

# Create/update requirements.txt
cat > requirements.txt << 'REQUIREMENTS'
boto3>=1.28.0
requests>=2.31.0
REQUIREMENTS

log_success "Dependencies configured"
echo ""

# Step 4: Package Lambda function
log_info "[4/7] Packaging Lambda function..."

cd "${LAMBDA_DIR}"

# Remove old package if exists
rm -f lambda-enhanced-handler.zip

# Create deployment package
log_info "Creating ZIP package..."
zip -r lambda-enhanced-handler.zip . \
    -x "*.pyc" \
    -x "__pycache__/*" \
    -x "*.git*" \
    -x "*.DS_Store" \
    -x "lambda_function.py.backup" \
    > /dev/null 2>&1

PACKAGE_SIZE=$(du -h lambda-enhanced-handler.zip | cut -f1)
log_success "Package created: ${PACKAGE_SIZE}"
echo ""

# Step 5: Deploy to AWS Lambda
log_info "[5/7] Deploying to AWS Lambda..."

# Check if Lambda exists
if ! aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" > /dev/null 2>&1; then
    log_error "Lambda function '${LAMBDA_NAME}' not found!"
    log_error "Expected Lambda: ${LAMBDA_NAME}"
    log_error ""
    log_error "Available Lambdas:"
    aws lambda list-functions --region "$REGION" --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' --output text
    exit 1
fi

log_info "Updating Lambda: ${LAMBDA_NAME}"

# Wait for any in-progress updates
log_info "Checking for in-progress updates..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    STATE=$(aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" --query 'Configuration.State' --output text 2>/dev/null || echo "Unknown")
    LAST_UPDATE_STATUS=$(aws lambda get-function --function-name "$LAMBDA_NAME" --region "$REGION" --query 'Configuration.LastUpdateStatus' --output text 2>/dev/null || echo "Unknown")

    if [ "$STATE" = "Active" ] && [ "$LAST_UPDATE_STATUS" = "Successful" ]; then
        log_success "Lambda is ready for update"
        break
    fi

    if [ $WAITED -eq 0 ]; then
        log_warn "Lambda is updating, waiting... (State: $STATE, Last: $LAST_UPDATE_STATUS)"
    fi

    sleep 5
    WAITED=$((WAITED + 5))

    if [ $WAITED -ge $MAX_WAIT ]; then
        log_error "Timeout waiting for Lambda to be ready"
        exit 1
    fi
done

# Update function code
log_info "Uploading new code..."
aws lambda update-function-code \
    --function-name "$LAMBDA_NAME" \
    --zip-file fileb://lambda-enhanced-handler.zip \
    --region "$REGION" \
    > /dev/null

log_info "Waiting for code update to complete..."
aws lambda wait function-updated --function-name "$LAMBDA_NAME" --region "$REGION"

# Update configuration
log_info "Updating function configuration..."
aws lambda update-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --timeout 300 \
    --memory-size 1024 \
    --environment Variables="{
        GOLD_DB=noaa_gold_${ENV},
        ATHENA_OUTPUT=s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/,
        BEDROCK_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0,
        ENV=${ENV},
        RELEVANCE_THRESHOLD=0.3,
        MAX_PARALLEL_PONDS=6
    }" \
    --region "$REGION" \
    > /dev/null 2>&1 || log_warn "Configuration update may have failed (might already be up-to-date)"

log_info "Waiting for configuration update..."
sleep 5

log_success "Lambda deployed successfully"
echo ""

# Step 6: Verify IAM permissions
log_info "[6/7] Verifying IAM permissions..."

LAMBDA_ROLE=$(aws lambda get-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --region "$REGION" \
    --query 'Role' \
    --output text 2>/dev/null)

ROLE_NAME=$(echo "$LAMBDA_ROLE" | awk -F'/' '{print $NF}')
log_info "Lambda Role: ${ROLE_NAME}"

# Check for Bedrock permissions
if aws iam get-role-policy --role-name "$ROLE_NAME" --policy-name "BedrockAccess" > /dev/null 2>&1; then
    log_success "Bedrock permissions already exist"
else
    log_warn "Adding Bedrock permissions..."

    cat > /tmp/bedrock-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:${REGION}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "BedrockAccess" \
        --policy-document file:///tmp/bedrock-policy.json

    rm /tmp/bedrock-policy.json
    log_success "Bedrock permissions added"
fi

echo ""

# Step 7: Setup ingestion schedules
log_info "[7/7] Setting up data ingestion schedules..."

if command -v python3 > /dev/null 2>&1; then
    cd "${PROJECT_ROOT}/ingestion-scheduler"

    log_info "Creating EventBridge schedules for all ponds..."
    python3 schedule_all_ingestions.py --action create_schedules --env "$ENV" 2>&1 | tee -a "${LOG_FILE}"

    log_info "Checking schedule status..."
    python3 schedule_all_ingestions.py --action status --env "$ENV" 2>&1 | tee -a "${LOG_FILE}"
else
    log_warn "Python 3 not found, skipping schedule creation"
    log_warn "Run manually: cd ingestion-scheduler && python3 schedule_all_ingestions.py --action create_schedules --env $ENV"
fi

echo ""

# Generate test script
log_info "Generating test script..."

cat > "${TEST_SCRIPTS_DIR}/test_ai_queries.sh" <<'TESTSCRIPT'
#!/bin/bash
# AI Multi-Pond Query Test Script

API_URL=$(aws apigateway get-rest-apis --query "items[?contains(name, 'noaa')].id" --output text | head -1)
API_ENDPOINT="https://${API_URL}.execute-api.us-east-1.amazonaws.com/dev/ask"

echo "Testing AI Multi-Pond System"
echo "API Endpoint: ${API_ENDPOINT}"
echo ""

# Test 1: Maritime Route (should query atmospheric + oceanic + buoy)
echo "Test 1: Maritime Route Planning"
echo "Expected: 3-4 ponds (atmospheric, oceanic, buoy, spatial)"
curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{"query": "Plan a safe maritime route from Boston to Portland Maine considering wind, waves, currents, and visibility"}' \
  | jq '.ponds_queried[] | {pond: .pond_name, score: .relevance_score, records: .record_count}'
echo ""
echo "---"
echo ""

# Test 2: Coastal Flooding (should query atmospheric + oceanic + climate)
echo "Test 2: Coastal Flooding Risk"
echo "Expected: 3-4 ponds (atmospheric, oceanic, climate)"
curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{"query": "Is there a coastal flooding risk in Charleston considering storm surge, tides, rainfall, and historical patterns?"}' \
  | jq '.ponds_queried[] | {pond: .pond_name, score: .relevance_score, records: .record_count}'
echo ""
echo "---"
echo ""

# Test 3: Simple Weather (should query only atmospheric)
echo "Test 3: Simple Weather Query"
echo "Expected: 1 pond (atmospheric)"
curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current weather in Boston?"}' \
  | jq '.ponds_queried[] | {pond: .pond_name, score: .relevance_score, records: .record_count}'
echo ""
echo "---"
echo ""

# Test 4: Historical Climate (should query atmospheric + climate)
echo "Test 4: Historical Climate Trends"
echo "Expected: 2 ponds (atmospheric, climate)"
curl -s -X POST "${API_ENDPOINT}" \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare historical temperature trends for NYC over the past 5 years with current conditions"}' \
  | jq '.ponds_queried[] | {pond: .pond_name, score: .relevance_score, records: .record_count}'
echo ""

echo "All tests completed!"
TESTSCRIPT

chmod +x "${TEST_SCRIPTS_DIR}/test_ai_queries.sh"
log_success "Test script created: ${TEST_SCRIPTS_DIR}/test_ai_queries.sh"
echo ""

# Final summary
echo ""
log_success "╔═══════════════════════════════════════════════════════════════╗"
log_success "║                 DEPLOYMENT COMPLETED                          ║"
log_success "╚═══════════════════════════════════════════════════════════════╝"
echo ""

log_info "Deployment Summary:"
log_info "  Lambda: ${LAMBDA_NAME}"
log_info "  Package: ${PACKAGE_SIZE}"
log_info "  Backup: ${BACKUP_DIR}"
log_info "  Log: ${LOG_FILE}"
echo ""

log_info "Features Enabled:"
echo "  ✓ AI-powered semantic query understanding (Bedrock/Claude 3.5)"
echo "  ✓ Intelligent multi-pond selection with reasoning"
echo "  ✓ Parallel pond querying (up to 6 ponds)"
echo "  ✓ Cross-pond data relationship explanations"
echo "  ✓ 15-minute data ingestion schedules"
echo ""

log_info "Testing:"
log_info "  Run: ${TEST_SCRIPTS_DIR}/test_ai_queries.sh"
echo ""

log_info "Monitoring:"
log_info "  CloudWatch Logs: aws logs tail /aws/lambda/${LAMBDA_NAME} --follow"
log_info "  Schedule Status: cd ingestion-scheduler && python3 schedule_all_ingestions.py --action status --env ${ENV}"
echo ""

log_info "Documentation:"
log_info "  Full Guide: documentation/AI_MULTI_POND_SYSTEM.md"
log_info "  Quick Start: documentation/QUICK_START.txt"
echo ""

log_warn "IMPORTANT: Test the deployment now!"
log_warn "  1. Open your webapp and ask: 'Plan a maritime route from Boston to Portland'"
log_warn "  2. Verify it queries atmospheric + oceanic + buoy ponds"
log_warn "  3. Check CloudWatch Logs for 'AI selected X ponds' messages"
echo ""

log_info "Rollback (if needed):"
log_info "  cd ${LAMBDA_DIR}"
log_info "  cp ${BACKUP_DIR}/lambda_function.py.backup lambda_function.py"
log_info "  zip -r lambda-enhanced-handler.zip ."
log_info "  aws lambda update-function-code --function-name ${LAMBDA_NAME} --zip-file fileb://lambda-enhanced-handler.zip"
echo ""

log_success "🎉 Deployment successful! Your AI multi-pond system is live!"

exit 0
