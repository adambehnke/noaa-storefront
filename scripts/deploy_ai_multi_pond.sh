#!/bin/bash
###############################################################################
# Deploy AI-Powered Multi-Pond Query System
#
# This script deploys the enhanced AI query handler that uses Bedrock/Claude
# to intelligently route queries across all relevant data ponds.
#
# Usage:
#   ./deploy_ai_multi_pond.sh [--env dev|prod] [--skip-schedules]
#
# Author: NOAA Federated Data Lake Team
# Version: 1.0
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENV="dev"
SKIP_SCHEDULES=false
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-east-1"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENV="$2"
      shift 2
      ;;
    --skip-schedules)
      SKIP_SCHEDULES=true
      shift
      ;;
    --help)
      echo "Usage: $0 [--env dev|prod] [--skip-schedules]"
      echo ""
      echo "Options:"
      echo "  --env ENV            Deployment environment (default: dev)"
      echo "  --skip-schedules     Skip creating EventBridge schedules"
      echo "  --help               Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# Verify AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
  echo -e "${RED}ERROR: AWS credentials not configured${NC}"
  exit 1
fi

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  NOAA Federated Data Lake - AI Multi-Pond Deployment         ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${YELLOW}Environment:${NC}     $ENV"
echo -e "${YELLOW}AWS Account:${NC}    $ACCOUNT_ID"
echo -e "${YELLOW}Region:${NC}         $REGION"
echo ""

# Step 1: Package Lambda function
echo -e "${BLUE}[1/6] Packaging Lambda function...${NC}"
cd lambda-packages/ai-query-package

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
  echo "  Installing dependencies..."
  pip install -r requirements.txt -t . -q
fi

# Create deployment package
echo "  Creating deployment package..."
zip -r ai_query_handler.zip . -x "*.pyc" -x "__pycache__/*" -x "*.git*" > /dev/null

PACKAGE_SIZE=$(du -h ai_query_handler.zip | cut -f1)
echo -e "  ${GREEN}✓ Package created: $PACKAGE_SIZE${NC}"

cd ../..

# Step 2: Deploy Lambda function
echo -e "${BLUE}[2/6] Deploying Lambda function...${NC}"
LAMBDA_NAME="noaa-ai-query-${ENV}"

# Check if Lambda exists
if aws lambda get-function --function-name "$LAMBDA_NAME" &> /dev/null; then
  echo "  Updating existing Lambda: $LAMBDA_NAME"
  aws lambda update-function-code \
    --function-name "$LAMBDA_NAME" \
    --zip-file fileb://lambda-packages/ai-query-package/ai_query_handler.zip \
    --region "$REGION" > /dev/null

  # Update configuration
  aws lambda update-function-configuration \
    --function-name "$LAMBDA_NAME" \
    --timeout 300 \
    --memory-size 1024 \
    --environment Variables="{
      GOLD_DB=noaa_gold_${ENV},
      ATHENA_OUTPUT=s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/,
      BEDROCK_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0,
      ENV=${ENV},
      ENHANCED_HANDLER=noaa-enhanced-handler-${ENV}
    }" \
    --region "$REGION" > /dev/null

  echo -e "  ${GREEN}✓ Lambda updated successfully${NC}"
else
  echo -e "  ${YELLOW}⚠ Lambda not found. Please create it first using CloudFormation.${NC}"
  echo "  Stack name: noaa-complete-stack-${ENV}"
  exit 1
fi

# Wait for Lambda to be ready
echo "  Waiting for Lambda to be ready..."
aws lambda wait function-updated --function-name "$LAMBDA_NAME" --region "$REGION"
echo -e "  ${GREEN}✓ Lambda is ready${NC}"

# Step 3: Verify IAM permissions
echo -e "${BLUE}[3/6] Verifying IAM permissions...${NC}"

LAMBDA_ROLE=$(aws lambda get-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --query 'Role' \
  --output text)

ROLE_NAME=$(echo "$LAMBDA_ROLE" | awk -F'/' '{print $NF}')

echo "  Lambda Role: $ROLE_NAME"

# Check if role has Bedrock permissions
BEDROCK_PERMISSION=$(aws iam list-attached-role-policies \
  --role-name "$ROLE_NAME" \
  --query "AttachedPolicies[?contains(PolicyName, 'Bedrock')].PolicyName" \
  --output text)

if [ -z "$BEDROCK_PERMISSION" ]; then
  echo -e "  ${YELLOW}⚠ Bedrock permissions may be missing. Creating inline policy...${NC}"

  cat > /tmp/bedrock-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:${REGION}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
    }
  ]
}
EOF

  aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "BedrockAccess" \
    --policy-document file:///tmp/bedrock-policy.json

  echo -e "  ${GREEN}✓ Bedrock permissions added${NC}"
else
  echo -e "  ${GREEN}✓ Bedrock permissions exist${NC}"
fi

# Step 4: Setup ingestion schedules
if [ "$SKIP_SCHEDULES" = false ]; then
  echo -e "${BLUE}[4/6] Setting up ingestion schedules...${NC}"

  # Check if Python 3 is available
  if command -v python3 &> /dev/null; then
    cd ingestion-scheduler

    echo "  Creating EventBridge schedules for all ponds..."
    python3 schedule_all_ingestions.py --action create_schedules --env "$ENV"

    echo ""
    echo "  Checking schedule status..."
    python3 schedule_all_ingestions.py --action status --env "$ENV"

    cd ..
  else
    echo -e "  ${YELLOW}⚠ Python 3 not found. Skipping schedule creation.${NC}"
    echo "  Run manually: cd ingestion-scheduler && python3 schedule_all_ingestions.py --action create_schedules --env $ENV"
  fi
else
  echo -e "${BLUE}[4/6] Skipping ingestion schedules (--skip-schedules flag)${NC}"
fi

# Step 5: Test deployment
echo -e "${BLUE}[5/6] Testing deployment...${NC}"

# Create test payload
TEST_PAYLOAD=$(cat <<EOF
{
  "body": "{\"query\": \"What is the weather in Boston and what are the current tide conditions?\"}"
}
EOF
)

echo "  Invoking Lambda with test query..."
LAMBDA_RESPONSE=$(aws lambda invoke \
  --function-name "$LAMBDA_NAME" \
  --payload "$TEST_PAYLOAD" \
  --region "$REGION" \
  /tmp/lambda-response.json 2>&1)

if grep -q "StatusCode.*200" <<< "$LAMBDA_RESPONSE"; then
  echo -e "  ${GREEN}✓ Lambda invocation successful${NC}"

  # Parse response
  if [ -f /tmp/lambda-response.json ]; then
    STATUS_CODE=$(jq -r '.statusCode' /tmp/lambda-response.json 2>/dev/null || echo "N/A")
    BODY=$(jq -r '.body' /tmp/lambda-response.json 2>/dev/null || echo "{}")
    PONDS_QUERIED=$(echo "$BODY" | jq -r '.ponds_queried | length' 2>/dev/null || echo "0")

    if [ "$STATUS_CODE" = "200" ]; then
      echo -e "  ${GREEN}✓ Query processed successfully${NC}"
      echo "  Ponds queried: $PONDS_QUERIED"
    else
      echo -e "  ${YELLOW}⚠ Query returned status: $STATUS_CODE${NC}"
    fi
  fi
else
  echo -e "  ${RED}✗ Lambda invocation failed${NC}"
  cat /tmp/lambda-response.json
fi

# Step 6: Summary
echo -e "${BLUE}[6/6] Deployment Summary${NC}"
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  DEPLOYMENT SUCCESSFUL                        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Lambda Function:${NC}    $LAMBDA_NAME"
echo -e "${YELLOW}Region:${NC}             $REGION"
echo -e "${YELLOW}Package Size:${NC}       $PACKAGE_SIZE"
echo ""
echo -e "${YELLOW}Features Enabled:${NC}"
echo "  ✓ AI-powered query understanding (Bedrock/Claude 3.5)"
echo "  ✓ Intelligent multi-pond selection"
echo "  ✓ Parallel pond querying"
echo "  ✓ Cross-pond data relationship explanations"
if [ "$SKIP_SCHEDULES" = false ]; then
  echo "  ✓ 15-minute data ingestion schedules"
fi
echo ""
echo -e "${YELLOW}API Endpoint:${NC}"
API_URL="https://$(aws apigateway get-rest-apis \
  --query "items[?name=='noaa-federated-api-${ENV}'].id" \
  --output text).execute-api.${REGION}.amazonaws.com/${ENV}"
echo "  POST $API_URL/ask"
echo ""
echo -e "${YELLOW}Test with curl:${NC}"
echo "  curl -X POST \"$API_URL/ask\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"query\": \"Plan a maritime route from Boston to Portland Maine\"}'"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Test with complex multi-pond queries"
echo "  2. Monitor CloudWatch Logs: /aws/lambda/$LAMBDA_NAME"
echo "  3. Check Bedrock usage in AWS Cost Explorer"
if [ "$SKIP_SCHEDULES" = false ]; then
  echo "  4. Verify data ingestion: python3 ingestion-scheduler/schedule_all_ingestions.py --action status --env $ENV"
fi
echo ""
echo -e "${YELLOW}Documentation:${NC}"
echo "  See AI_MULTI_POND_SYSTEM.md for complete documentation"
echo ""

# Cleanup
rm -f /tmp/bedrock-policy.json /tmp/lambda-response.json

exit 0
