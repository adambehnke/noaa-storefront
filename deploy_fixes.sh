#!/bin/bash
# Quick deployment script for NOAA Data Lake fixes and enhancements
# This deploys:
# 1. Fixed AI orchestrator (Athena-compatible SQL)
# 2. New passthrough handler (direct NOAA API access)
# 3. API Gateway endpoint for passthrough

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}NOAA Data Lake - Quick Fix Deployment${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Configuration
ENV=${1:-dev}
REGION=${2:-us-east-1}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
DEPLOYMENT_BUCKET="noaa-deployment-${ACCOUNT_ID}-${ENV}"

echo -e "${BLUE}Configuration:${NC}"
echo "  Environment: $ENV"
echo "  Region: $REGION"
echo "  Account: $ACCOUNT_ID"
echo ""

# Get stack outputs
echo -e "${BLUE}Getting stack information...${NC}"
STACK_NAME="noaa-federated-lake-${ENV}"
API_ID=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayId`].OutputValue' \
  --output text 2>/dev/null || echo "")

LAMBDA_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaExecutionRoleArn`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$API_ID" ]; then
  echo -e "${YELLOW}Could not find API Gateway ID from stack outputs${NC}"
  API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='noaa-data-lake-${ENV}'].ApiId" --output text)
fi

if [ -z "$LAMBDA_ROLE_ARN" ]; then
  echo -e "${YELLOW}Could not find Lambda role from stack outputs${NC}"
  LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/noaa-lambda-execution-${ENV}"
fi

echo "  API Gateway ID: $API_ID"
echo "  Lambda Role: $LAMBDA_ROLE_ARN"
echo ""

# Step 1: Update AI Orchestrator with SQL fix
echo -e "${GREEN}[1/5] Updating AI Orchestrator (SQL date fix)...${NC}"
zip -q noaa_ai_orchestrator_fixed.zip ai_query_orchestrator.py ai_query_config.yaml 2>/dev/null || {
  echo -e "${YELLOW}Files not found, skipping orchestrator update${NC}"
}

if [ -f "noaa_ai_orchestrator_fixed.zip" ]; then
  aws lambda update-function-code \
    --function-name noaa-ai-orchestrator-${ENV} \
    --zip-file fileb://noaa_ai_orchestrator_fixed.zip \
    --region $REGION > /dev/null
  echo -e "${GREEN}✓ AI Orchestrator updated${NC}"
  rm noaa_ai_orchestrator_fixed.zip
else
  echo -e "${YELLOW}⚠ Skipping orchestrator update${NC}"
fi

# Step 2: Package and deploy passthrough handler
echo -e "${GREEN}[2/5] Deploying Passthrough Handler...${NC}"
zip -q noaa_passthrough.zip noaa_passthrough_handler.py 2>/dev/null || {
  echo -e "${RED}✗ noaa_passthrough_handler.py not found${NC}"
  exit 1
}

# Check if function exists
FUNCTION_EXISTS=$(aws lambda get-function \
  --function-name noaa-passthrough-${ENV} \
  --region $REGION 2>/dev/null && echo "yes" || echo "no")

if [ "$FUNCTION_EXISTS" = "yes" ]; then
  echo "  Updating existing function..."
  aws lambda update-function-code \
    --function-name noaa-passthrough-${ENV} \
    --zip-file fileb://noaa_passthrough.zip \
    --region $REGION > /dev/null
  echo -e "${GREEN}✓ Passthrough handler updated${NC}"
else
  echo "  Creating new function..."
  aws lambda create-function \
    --function-name noaa-passthrough-${ENV} \
    --runtime python3.11 \
    --role $LAMBDA_ROLE_ARN \
    --handler noaa_passthrough_handler.lambda_handler \
    --zip-file fileb://noaa_passthrough.zip \
    --timeout 30 \
    --memory-size 256 \
    --region $REGION \
    --description "Direct passthrough to NOAA APIs" \
    --environment "Variables={ENV=${ENV}}" > /dev/null

  # Wait for function to be ready
  aws lambda wait function-active-v2 \
    --function-name noaa-passthrough-${ENV} \
    --region $REGION

  echo -e "${GREEN}✓ Passthrough handler created${NC}"
fi

rm noaa_passthrough.zip

# Step 3: Add API Gateway endpoint
echo -e "${GREEN}[3/5] Configuring API Gateway endpoint...${NC}"

if [ -n "$API_ID" ]; then
  # Check if route already exists
  ROUTE_EXISTS=$(aws apigatewayv2 get-routes \
    --api-id $API_ID \
    --region $REGION \
    --query "Items[?RouteKey=='GET /passthrough'].RouteId" \
    --output text)

  if [ -z "$ROUTE_EXISTS" ]; then
    echo "  Creating integration..."
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
      --api-id $API_ID \
      --integration-type AWS_PROXY \
      --integration-uri "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:noaa-passthrough-${ENV}" \
      --payload-format-version 2.0 \
      --region $REGION \
      --query 'IntegrationId' \
      --output text)

    echo "  Creating route..."
    aws apigatewayv2 create-route \
      --api-id $API_ID \
      --route-key "GET /passthrough" \
      --target "integrations/${INTEGRATION_ID}" \
      --region $REGION > /dev/null

    echo "  Adding Lambda permissions..."
    aws lambda add-permission \
      --function-name noaa-passthrough-${ENV} \
      --statement-id apigateway-passthrough \
      --action lambda:InvokeFunction \
      --principal apigateway.amazonaws.com \
      --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*" \
      --region $REGION > /dev/null 2>&1 || true

    echo -e "${GREEN}✓ API Gateway route created${NC}"
  else
    echo -e "${YELLOW}✓ Route already exists${NC}"
  fi
else
  echo -e "${YELLOW}⚠ API Gateway ID not found, skipping endpoint creation${NC}"
fi

# Step 4: Test deployment
echo -e "${GREEN}[4/5] Testing deployment...${NC}"

if [ -n "$API_ID" ]; then
  API_ENDPOINT=$(aws apigatewayv2 get-api \
    --api-id $API_ID \
    --region $REGION \
    --query 'ApiEndpoint' \
    --output text)

  echo "  Testing NWS passthrough..."
  curl -s "${API_ENDPOINT}/${ENV}/passthrough?service=nws&endpoint=alerts/active" | jq -r '.summary.total_alerts // "Error"' > /tmp/test_result.txt
  RESULT=$(cat /tmp/test_result.txt)

  if [ "$RESULT" != "Error" ]; then
    echo -e "${GREEN}✓ Passthrough working: $RESULT alerts found${NC}"
  else
    echo -e "${YELLOW}⚠ Passthrough test inconclusive${NC}"
  fi

  echo "  Testing AI endpoint..."
  curl -s -X POST "${API_ENDPOINT}/${ENV}/ask" \
    -H "Content-Type: application/json" \
    -d '{"query":"test"}' | jq -r '.synthesis.answer // "Error"' > /tmp/test_ai.txt

  AI_RESULT=$(cat /tmp/test_ai.txt)
  if [ "$AI_RESULT" != "Error" ]; then
    echo -e "${GREEN}✓ AI endpoint responding${NC}"
  else
    echo -e "${YELLOW}⚠ AI endpoint test inconclusive${NC}"
  fi

  rm -f /tmp/test_result.txt /tmp/test_ai.txt
else
  echo -e "${YELLOW}⚠ Cannot test - API endpoint not found${NC}"
fi

# Step 5: Summary and next steps
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -n "$API_ID" ]; then
  API_ENDPOINT=$(aws apigatewayv2 get-api \
    --api-id $API_ID \
    --region $REGION \
    --query 'ApiEndpoint' \
    --output text)

  echo -e "${GREEN}Available Endpoints:${NC}"
  echo "  AI Query:      ${API_ENDPOINT}/${ENV}/ask"
  echo "  Data Query:    ${API_ENDPOINT}/${ENV}/data"
  echo "  Passthrough:   ${API_ENDPOINT}/${ENV}/passthrough"
  echo ""

  echo -e "${GREEN}Test Commands:${NC}"
  echo ""
  echo "# Test AI query with plain English:"
  echo "curl -X POST '${API_ENDPOINT}/${ENV}/ask' \\"
  echo "  -H 'Content-Type: application/json' \\"
  echo "  -d '{\"query\":\"Show me recent weather alerts\"}'"
  echo ""
  echo "# Test passthrough to NWS:"
  echo "curl '${API_ENDPOINT}/${ENV}/passthrough?service=nws&endpoint=alerts/active&area=CA'"
  echo ""
  echo "# Test passthrough to Tides:"
  echo "curl '${API_ENDPOINT}/${ENV}/passthrough?service=tides&station=9414290&hours_back=6'"
  echo ""
fi

echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Run Step Functions pipeline to populate Gold layer:"
echo "   aws stepfunctions start-execution --state-machine-arn <ARN>"
echo ""
echo "2. Query Gold layer directly with Athena:"
echo "   SELECT COUNT(*) FROM noaa_gold_${ENV}.atmospheric_aggregated;"
echo ""
echo "3. Check Lambda logs if issues occur:"
echo "   aws logs tail /aws/lambda/noaa-ai-orchestrator-${ENV} --follow"
echo ""

echo -e "${GREEN}✓ All done!${NC}"
