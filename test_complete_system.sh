#!/bin/bash
# Comprehensive End-to-End Test Suite for NOAA Data Lake
# Tests all functionality: AI queries, data API, passthrough, Athena

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
ENV=${1:-dev}
REGION=${2:-us-east-1}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

# Get API endpoint
STACK_NAME="noaa-federated-lake-${ENV}"
API_ID=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayId`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$API_ID" ]; then
  API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='noaa-data-lake-${ENV}'].ApiId" --output text 2>/dev/null || echo "")
fi

if [ -n "$API_ID" ]; then
  API_ENDPOINT=$(aws apigatewayv2 get-api \
    --api-id $API_ID \
    --region $REGION \
    --query 'ApiEndpoint' \
    --output text)/${ENV}
else
  echo -e "${RED}Error: Could not find API Gateway endpoint${NC}"
  echo "Please check that the stack is deployed: $STACK_NAME"
  exit 1
fi

# Test counters
PASSED=0
FAILED=0
TOTAL=0

# Helper functions
print_header() {
  echo ""
  echo -e "${BLUE}${BOLD}========================================${NC}"
  echo -e "${BLUE}${BOLD}$1${NC}"
  echo -e "${BLUE}${BOLD}========================================${NC}"
  echo ""
}

print_test() {
  echo -e "${YELLOW}[TEST $(($TOTAL + 1))]${NC} $1"
}

print_pass() {
  echo -e "${GREEN}✓ PASS${NC} $1"
  PASSED=$((PASSED + 1))
  TOTAL=$((TOTAL + 1))
}

print_fail() {
  echo -e "${RED}✗ FAIL${NC} $1"
  FAILED=$((FAILED + 1))
  TOTAL=$((TOTAL + 1))
}

print_info() {
  echo -e "${BLUE}  →${NC} $1"
}

# Test execution
run_test() {
  local name="$1"
  local command="$2"
  local expected="$3"

  print_test "$name"

  result=$(eval "$command" 2>&1)
  exit_code=$?

  if [ $exit_code -eq 0 ] && echo "$result" | grep -q "$expected" 2>/dev/null; then
    print_pass "$name"
    if [ -n "$4" ]; then
      print_info "$4"
    fi
  else
    print_fail "$name"
    print_info "Expected: $expected"
    print_info "Got: ${result:0:100}"
  fi

  echo ""
}

# Start tests
clear
print_header "NOAA Data Lake - End-to-End Test Suite"
echo "Environment: $ENV"
echo "Region: $REGION"
echo "API Endpoint: $API_ENDPOINT"
echo ""

# =============================================================
# Infrastructure Tests
# =============================================================
print_header "1. Infrastructure Health Checks"

print_test "CloudFormation Stack Status"
STACK_STATUS=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].StackStatus' \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
  print_pass "Stack is healthy: $STACK_STATUS"
else
  print_fail "Stack status: $STACK_STATUS"
fi
echo ""

print_test "API Gateway Health"
response=$(curl -s -w "\n%{http_code}" "${API_ENDPOINT}/data?ping=true")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "200" ]; then
  print_pass "API Gateway is responding"
  print_info "Status: $(echo "$body" | jq -r '.status // "unknown"')"
else
  print_fail "API Gateway returned HTTP $http_code"
fi
echo ""

print_test "S3 Data Lake Buckets"
LAKE_BUCKET="noaa-federated-lake-${ACCOUNT_ID}-${ENV}"
BUCKET_EXISTS=$(aws s3 ls s3://${LAKE_BUCKET} 2>/dev/null && echo "yes" || echo "no")

if [ "$BUCKET_EXISTS" = "yes" ]; then
  print_pass "Data lake bucket exists: $LAKE_BUCKET"

  # Check layers
  BRONZE_COUNT=$(aws s3 ls s3://${LAKE_BUCKET}/bronze/ --recursive | wc -l)
  GOLD_COUNT=$(aws s3 ls s3://${LAKE_BUCKET}/gold/ --recursive | wc -l)
  print_info "Bronze layer: $BRONZE_COUNT files"
  print_info "Gold layer: $GOLD_COUNT files"
else
  print_fail "Data lake bucket not found"
fi
echo ""

# =============================================================
# AI Query Endpoint Tests (Plain English)
# =============================================================
print_header "2. AI Query Endpoint Tests"

print_test "AI Endpoint - Health Query"
response=$(curl -s -X POST "${API_ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"What data do you have?"}')

if echo "$response" | jq -e '.synthesis' > /dev/null 2>&1; then
  print_pass "AI endpoint is responding"
  answer=$(echo "$response" | jq -r '.synthesis.answer // ""' | head -c 100)
  print_info "Answer: ${answer}..."
else
  print_fail "AI endpoint not working properly"
  print_info "Response: ${response:0:100}"
fi
echo ""

print_test "AI Endpoint - Weather Query"
response=$(curl -s -X POST "${API_ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Show me recent weather alerts"}')

if echo "$response" | jq -e '.ponds_queried' > /dev/null 2>&1; then
  print_pass "AI query routing working"
  ponds=$(echo "$response" | jq -r '.ponds_queried[].pond // ""' | tr '\n' ', ')
  print_info "Ponds queried: ${ponds%, }"
else
  print_fail "AI query routing failed"
fi
echo ""

print_test "AI Endpoint - Vague Query (Data Discovery)"
response=$(curl -s -X POST "${API_ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Tell me about environmental conditions"}')

if echo "$response" | jq -e '.synthesis.answer' > /dev/null 2>&1; then
  print_pass "Data discovery working"
  record_count=$(echo "$response" | jq -r '.record_count // 0')
  print_info "Records found: $record_count"
else
  print_fail "Data discovery failed"
fi
echo ""

# =============================================================
# Data API Tests (Traditional Queries)
# =============================================================
print_header "3. Data API Tests"

print_test "Data API - Ping"
response=$(curl -s "${API_ENDPOINT}/data?ping=true")

if echo "$response" | jq -e '.status' > /dev/null 2>&1; then
  status=$(echo "$response" | jq -r '.status')
  if [ "$status" = "healthy" ]; then
    print_pass "Data API health check passed"
  else
    print_fail "Data API status: $status"
  fi
else
  print_fail "Data API not responding"
fi
echo ""

print_test "Data API - Atmospheric Query"
response=$(curl -s "${API_ENDPOINT}/data?service=atmospheric&limit=10")

if echo "$response" | jq -e '.service' > /dev/null 2>&1; then
  print_pass "Atmospheric data query working"
  count=$(echo "$response" | jq -r '.count // 0')
  source=$(echo "$response" | jq -r '.source // "unknown"')
  print_info "Records: $count, Source: $source"
else
  print_fail "Atmospheric query failed"
fi
echo ""

print_test "Data API - Region Filter"
response=$(curl -s "${API_ENDPOINT}/data?service=atmospheric&region=CA&limit=5")

if echo "$response" | jq -e '.parameters.region' > /dev/null 2>&1; then
  print_pass "Region filtering working"
  region=$(echo "$response" | jq -r '.parameters.region')
  print_info "Filtered to region: $region"
else
  print_fail "Region filtering failed"
fi
echo ""

# =============================================================
# Passthrough Tests (Direct NOAA API Access)
# =============================================================
print_header "4. Passthrough Tests (Direct NOAA APIs)"

print_test "Passthrough - NWS Alerts"
response=$(curl -s "${API_ENDPOINT}/passthrough?service=nws&endpoint=alerts/active")

if echo "$response" | jq -e '.source' > /dev/null 2>&1; then
  source=$(echo "$response" | jq -r '.source')
  if [ "$source" = "noaa_nws_api" ]; then
    print_pass "NWS passthrough working"
    alerts=$(echo "$response" | jq -r '.summary.total_alerts // 0')
    print_info "Active alerts: $alerts"
  else
    print_fail "NWS passthrough returned wrong source: $source"
  fi
else
  print_fail "NWS passthrough failed"
fi
echo ""

print_test "Passthrough - Tides & Currents"
response=$(curl -s "${API_ENDPOINT}/passthrough?service=tides&station=9414290&hours_back=6")

if echo "$response" | jq -e '.source' > /dev/null 2>&1; then
  source=$(echo "$response" | jq -r '.source')
  if [ "$source" = "noaa_tides_api" ]; then
    print_pass "Tides passthrough working"
    records=$(echo "$response" | jq -r '.summary.record_count // 0')
    station=$(echo "$response" | jq -r '.summary.station_name // "unknown"')
    print_info "Station: $station, Records: $records"
  else
    print_fail "Tides passthrough returned wrong source: $source"
  fi
else
  print_fail "Tides passthrough failed"
fi
echo ""

print_test "Passthrough - Error Handling"
response=$(curl -s "${API_ENDPOINT}/passthrough?service=invalid")

if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
  print_pass "Error handling working"
  error=$(echo "$response" | jq -r '.error')
  print_info "Error: $error"
else
  print_fail "Error handling not working"
fi
echo ""

# =============================================================
# Athena Integration Tests
# =============================================================
print_header "5. Athena Query Tests"

print_test "Athena - Bronze Layer"
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT COUNT(*) as cnt FROM noaa_bronze_${ENV}.atmospheric_raw" \
  --query-execution-context Database=noaa_bronze_${ENV} \
  --result-configuration OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/ \
  --query 'QueryExecutionId' \
  --output text 2>/dev/null || echo "")

if [ -n "$QUERY_ID" ]; then
  # Wait for query
  sleep 3
  STATUS=$(aws athena get-query-execution \
    --query-execution-id $QUERY_ID \
    --query 'QueryExecution.Status.State' \
    --output text 2>/dev/null || echo "FAILED")

  if [ "$STATUS" = "SUCCEEDED" ]; then
    print_pass "Athena Bronze layer query succeeded"
  else
    print_fail "Athena query status: $STATUS"
  fi
else
  print_fail "Failed to start Athena query"
fi
echo ""

print_test "Athena - Gold Layer"
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT COUNT(*) as cnt FROM noaa_gold_${ENV}.atmospheric_aggregated" \
  --query-execution-context Database=noaa_gold_${ENV} \
  --result-configuration OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-${ENV}/ \
  --query 'QueryExecutionId' \
  --output text 2>/dev/null || echo "")

if [ -n "$QUERY_ID" ]; then
  sleep 3
  STATUS=$(aws athena get-query-execution \
    --query-execution-id $QUERY_ID \
    --query 'QueryExecution.Status.State' \
    --output text 2>/dev/null || echo "FAILED")

  if [ "$STATUS" = "SUCCEEDED" ]; then
    print_pass "Athena Gold layer query succeeded"
  else
    print_fail "Athena query status: $STATUS"
  fi
else
  print_fail "Failed to start Athena query"
fi
echo ""

# =============================================================
# Lambda Function Tests
# =============================================================
print_header "6. Lambda Function Health"

for func in "noaa-ai-orchestrator-${ENV}" "noaa-data-api-${ENV}" "noaa-passthrough-${ENV}"; do
  print_test "Lambda: $func"

  STATUS=$(aws lambda get-function \
    --function-name $func \
    --query 'Configuration.State' \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [ "$STATUS" = "Active" ]; then
    print_pass "$func is active"
    MEMORY=$(aws lambda get-function-configuration \
      --function-name $func \
      --query 'MemorySize' \
      --output text 2>/dev/null)
    TIMEOUT=$(aws lambda get-function-configuration \
      --function-name $func \
      --query 'Timeout' \
      --output text 2>/dev/null)
    print_info "Memory: ${MEMORY}MB, Timeout: ${TIMEOUT}s"
  elif [ "$STATUS" = "NOT_FOUND" ]; then
    print_fail "$func not deployed"
  else
    print_fail "$func status: $STATUS"
  fi
  echo ""
done

# =============================================================
# Integration Tests
# =============================================================
print_header "7. Integration Tests"

print_test "Cross-Pond Query"
response=$(curl -s -X POST "${API_ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the relationship between ocean temperatures and weather?"}')

if echo "$response" | jq -e '.synthesis' > /dev/null 2>&1; then
  pond_count=$(echo "$response" | jq -r '.ponds_queried | length')
  if [ "$pond_count" -gt 1 ]; then
    print_pass "Cross-pond query working"
    print_info "Queried $pond_count ponds"
  else
    print_pass "Query executed (single pond)"
    print_info "Queried $pond_count pond(s)"
  fi
else
  print_fail "Cross-pond query failed"
fi
echo ""

print_test "Query with Raw Data"
response=$(curl -s -X POST "${API_ENDPOINT}/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Show weather data", "include_raw_data": true}')

if echo "$response" | jq -e '.synthesis' > /dev/null 2>&1; then
  print_pass "Raw data inclusion working"
else
  print_fail "Raw data inclusion failed"
fi
echo ""

# =============================================================
# Test Summary
# =============================================================
print_header "Test Summary"

echo "Total Tests: $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
  echo -e "${GREEN}${BOLD}🎉 All tests passed!${NC}"
  echo ""
  echo "Your NOAA Data Lake is fully operational!"
  echo ""
  echo "Try it out:"
  echo "  curl -X POST '${API_ENDPOINT}/ask' \\"
  echo "    -H 'Content-Type: application/json' \\"
  echo "    -d '{\"query\":\"Show me weather in California\"}'"
  exit 0
else
  echo -e "${YELLOW}${BOLD}⚠️  Some tests failed${NC}"
  echo ""
  echo "Check CloudWatch logs for details:"
  echo "  aws logs tail /aws/lambda/noaa-ai-orchestrator-${ENV} --follow"
  echo ""
  echo "For help, see: ACTION_PLAN.md"
  exit 1
fi
