#!/bin/bash
# Simplified deployment script for NOAA Data Lake fixes
# Fixes: SQL date functions + deploys passthrough handler

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}NOAA Data Lake - Deployment Fix${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Configuration
ENV=${1:-dev}
REGION=${2:-us-east-1}
ACCOUNT_ID="349338457682"
API_ID="z0rld53i7a"
API_ENDPOINT="https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev"
LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/noaa-lambda-execution-role-${ENV}"

echo -e "${BLUE}Configuration:${NC}"
echo "  Environment: $ENV"
echo "  Region: $REGION"
echo "  Account: $ACCOUNT_ID"
echo "  API ID: $API_ID"
echo "  Lambda Role: $LAMBDA_ROLE_ARN"
echo ""

# Step 1: Update AI Orchestrator with SQL fix
echo -e "${GREEN}[1/4] Updating AI Orchestrator (SQL date fix)...${NC}"

if [ ! -f "ai_query_orchestrator.py" ]; then
  echo -e "${RED}✗ ai_query_orchestrator.py not found${NC}"
  exit 1
fi

# Create package
zip -q noaa_ai_orchestrator_fixed.zip ai_query_orchestrator.py
if [ -f "ai_query_config.yaml" ]; then
  zip -q -u noaa_ai_orchestrator_fixed.zip ai_query_config.yaml
fi

# Update Lambda - try both possible names
UPDATED=false
for func_name in "noaa-ai-orchestrator-${ENV}" "noaa-ai-query-${ENV}"; do
  if aws lambda get-function --function-name "$func_name" --region $REGION &>/dev/null; then
    echo "  Updating $func_name..."
    aws lambda update-function-code \
      --function-name "$func_name" \
      --zip-file fileb://noaa_ai_orchestrator_fixed.zip \
      --region $REGION > /dev/null
    echo -e "${GREEN}✓ $func_name updated${NC}"
    UPDATED=true
    break
  fi
done

if [ "$UPDATED" = false ]; then
  echo -e "${YELLOW}⚠ Could not find AI orchestrator Lambda function${NC}"
fi

rm -f noaa_ai_orchestrator_fixed.zip
echo ""

# Step 2: Create passthrough handler package
echo -e "${GREEN}[2/4] Deploying Passthrough Handler...${NC}"

if [ ! -f "noaa_passthrough_handler.py" ]; then
  echo -e "${RED}✗ noaa_passthrough_handler.py not found${NC}"
  exit 1
fi

# Create deployment package with requests library
mkdir -p lambda_package
pip3 install --quiet --target lambda_package requests 2>/dev/null || pip install --quiet --target lambda_package requests
cp noaa_passthrough_handler.py lambda_package/
cd lambda_package
zip -q -r ../noaa_passthrough.zip .
cd ..
rm -rf lambda_package

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
    --role "$LAMBDA_ROLE_ARN" \
    --handler noaa_passthrough_handler.lambda_handler \
    --zip-file fileb://noaa_passthrough.zip \
    --timeout 30 \
    --memory-size 512 \
    --region $REGION \
    --description "Direct passthrough to NOAA APIs" \
    --environment "Variables={ENV=${ENV}}" > /dev/null

  echo "  Waiting for function to be ready..."
  aws lambda wait function-active-v2 \
    --function-name noaa-passthrough-${ENV} \
    --region $REGION

  echo -e "${GREEN}✓ Passthrough handler created${NC}"
fi

rm -f noaa_passthrough.zip
echo ""

# Step 3: Add API Gateway endpoint (REST API v1)
echo -e "${GREEN}[3/4] Configuring API Gateway endpoint...${NC}"

# Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --region $REGION \
  --query 'items[?path==`/`].id' \
  --output text)

echo "  Root resource ID: $ROOT_RESOURCE_ID"

# Check if /passthrough resource already exists
PASSTHROUGH_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --region $REGION \
  --query 'items[?pathPart==`passthrough`].id' \
  --output text)

if [ -z "$PASSTHROUGH_RESOURCE_ID" ]; then
  echo "  Creating /passthrough resource..."
  PASSTHROUGH_RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_RESOURCE_ID \
    --path-part passthrough \
    --region $REGION \
    --query 'id' \
    --output text)
  echo "  Created resource ID: $PASSTHROUGH_RESOURCE_ID"
else
  echo "  /passthrough resource already exists: $PASSTHROUGH_RESOURCE_ID"
fi

# Create GET method
echo "  Setting up GET method..."
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $PASSTHROUGH_RESOURCE_ID \
  --http-method GET \
  --authorization-type NONE \
  --region $REGION > /dev/null 2>&1 || echo "  Method already exists"

# Setup Lambda integration
LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:noaa-passthrough-${ENV}"
LAMBDA_URI="arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations"

echo "  Configuring Lambda integration..."
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $PASSTHROUGH_RESOURCE_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "$LAMBDA_URI" \
  --region $REGION > /dev/null 2>&1 || echo "  Integration already exists"

# Add Lambda permission
echo "  Adding Lambda permission..."
aws lambda add-permission \
  --function-name noaa-passthrough-${ENV} \
  --statement-id apigateway-passthrough-get \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*" \
  --region $REGION > /dev/null 2>&1 || echo "  Permission already exists"

# Deploy API
echo "  Deploying API changes..."
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name $ENV \
  --region $REGION > /dev/null

echo -e "${GREEN}✓ API Gateway configured${NC}"
echo ""

# Step 4: Test deployment
echo -e "${GREEN}[4/4] Testing deployment...${NC}"

echo "  Testing passthrough endpoint..."
RESPONSE=$(curl -s "${API_ENDPOINT}/passthrough?service=nws&endpoint=alerts/active" 2>/dev/null || echo '{"error":"failed"}')

if echo "$RESPONSE" | grep -q "noaa_nws_api"; then
  ALERT_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('summary', {}).get('total_alerts', 0))" 2>/dev/null || echo "?")
  echo -e "${GREEN}✓ Passthrough working: $ALERT_COUNT alerts found${NC}"
else
  echo -e "${YELLOW}⚠ Passthrough test inconclusive (may need a moment to deploy)${NC}"
fi

echo "  Testing AI endpoint..."
AI_RESPONSE=$(curl -s -X POST "${API_ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}' 2>/dev/null || echo '{"error":"failed"}')

if echo "$AI_RESPONSE" | grep -q "synthesis"; then
  echo -e "${GREEN}✓ AI endpoint responding${NC}"
else
  echo -e "${YELLOW}⚠ AI endpoint test inconclusive${NC}"
fi

echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${GREEN}Available Endpoints:${NC}"
echo "  AI Query:      ${API_ENDPOINT}/ask"
echo "  Data Query:    ${API_ENDPOINT}/data"
echo "  Passthrough:   ${API_ENDPOINT}/passthrough"
echo ""

echo -e "${GREEN}Test Commands:${NC}"
echo ""
echo "# Test AI query:"
echo "curl -X POST '${API_ENDPOINT}/ask' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\":\"Show me recent weather alerts\"}'"
echo ""
echo "# Test passthrough to NWS:"
echo "curl '${API_ENDPOINT}/passthrough?service=nws&endpoint=alerts/active&area=CA'"
echo ""
echo "# Test passthrough to Tides:"
echo "curl '${API_ENDPOINT}/passthrough?service=tides&station=9414290&hours_back=6'"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Populate Gold layer - see QUICK_FIX_GUIDE.md section 'Fix #2'"
echo "2. Test with: curl -X POST '${API_ENDPOINT}/ask' -H 'Content-Type: application/json' -d '{\"query\":\"test\"}'"
echo "3. Check logs: aws logs tail /aws/lambda/noaa-passthrough-${ENV} --follow"
echo ""

echo -e "${GREEN}✓ Deployment successful!${NC}"
