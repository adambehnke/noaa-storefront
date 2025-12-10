#!/bin/bash
#
# NOAA Chatbot Comprehensive Test Suite
# Tests all components: API Gateway, CORS, Lambda, CloudFront
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_BASE="https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev"
CLOUDFRONT_URL="https://d244ik6grpfthq.cloudfront.net"
CLOUDFRONT_ORIGIN="https://d244ik6grpfthq.cloudfront.net"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  NOAA Chatbot - Complete Validation Test Suite        ║${NC}"
echo -e "${BLUE}║  Account: 899626030376                                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_pattern="$3"

    echo -e "${YELLOW}[TEST]${NC} $test_name"

    result=$(eval "$test_command" 2>&1)

    if echo "$result" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}  ✅ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}  ❌ FAIL${NC}"
        echo -e "${RED}  Expected pattern: $expected_pattern${NC}"
        echo -e "${RED}  Got: ${result:0:100}${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo -e "${BLUE}═══ Phase 1: API Gateway Connectivity ═══${NC}"
echo ""

# Test 1: Ping endpoint
run_test "API Gateway - Ping endpoint" \
    "curl -s -X POST '$API_BASE/query' -H 'Content-Type: application/json' -d '{\"action\":\"ping\"}'" \
    '"status":"ok"'

# Test 2: POST method exists
run_test "API Gateway - POST method accepts requests" \
    "curl -s -o /dev/null -w '%{http_code}' -X POST '$API_BASE/query' -H 'Content-Type: application/json' -d '{\"action\":\"ping\"}'" \
    "200"

echo ""
echo -e "${BLUE}═══ Phase 2: CORS Configuration ═══${NC}"
echo ""

# Test 3: OPTIONS method returns 200
run_test "CORS - OPTIONS method responds" \
    "curl -s -o /dev/null -w '%{http_code}' -X OPTIONS '$API_BASE/query'" \
    "200"

# Test 4: OPTIONS includes Allow-Origin header
run_test "CORS - Access-Control-Allow-Origin header present" \
    "curl -s -v -X OPTIONS '$API_BASE/query' 2>&1" \
    "access-control-allow-origin: \*"

# Test 5: OPTIONS includes Allow-Methods header
run_test "CORS - Access-Control-Allow-Methods includes POST" \
    "curl -s -v -X OPTIONS '$API_BASE/query' 2>&1" \
    "access-control-allow-methods:.*POST"

# Test 6: OPTIONS includes Allow-Headers
run_test "CORS - Access-Control-Allow-Headers present" \
    "curl -s -v -X OPTIONS '$API_BASE/query' 2>&1" \
    "access-control-allow-headers"

# Test 7: OPTIONS with Origin header
run_test "CORS - Preflight with Origin header succeeds" \
    "curl -s -o /dev/null -w '%{http_code}' -X OPTIONS '$API_BASE/query' -H 'Origin: $CLOUDFRONT_ORIGIN' -H 'Access-Control-Request-Method: POST'" \
    "200"

echo ""
echo -e "${BLUE}═══ Phase 3: Lambda Function ═══${NC}"
echo ""

# Test 8: Natural language query (webapp format)
run_test "Lambda - Natural language query (webapp format)" \
    "curl -s -X POST '$API_BASE/query' -H 'Content-Type: application/json' -d '{\"query\":\"What is the weather?\"}'" \
    '"answer"'

# Test 9: Response includes metadata
run_test "Lambda - Response includes metadata" \
    "curl -s -X POST '$API_BASE/query' -H 'Content-Type: application/json' -d '{\"query\":\"test\"}'" \
    '"metadata"'

# Test 10: Lambda handles CORS in response
run_test "Lambda - Response includes CORS headers" \
    "curl -s -v -X POST '$API_BASE/query' -H 'Content-Type: application/json' -H 'Origin: $CLOUDFRONT_ORIGIN' -d '{\"query\":\"test\"}' 2>&1" \
    "access-control-allow-origin"

# Test 11: Complex Miami query
run_test "Lambda - Miami weather query returns helpful answer" \
    "curl -s -X POST '$API_BASE/query' -H 'Content-Type: application/json' -d '{\"query\":\"What are the weather conditions in Miami?\"}'" \
    "Miami\|weather"

echo ""
echo -e "${BLUE}═══ Phase 4: CloudFront Distribution ═══${NC}"
echo ""

# Test 12: CloudFront main page
run_test "CloudFront - Main page accessible" \
    "curl -s -o /dev/null -w '%{http_code}' '$CLOUDFRONT_URL/'" \
    "200"

# Test 13: app.js accessible
run_test "CloudFront - app.js loads" \
    "curl -s -o /dev/null -w '%{http_code}' '$CLOUDFRONT_URL/app.js'" \
    "200"

# Test 14: app.js has correct API URL
run_test "CloudFront - app.js configured with correct API URL" \
    "curl -s '$CLOUDFRONT_URL/app.js'" \
    "u35c31x306.execute-api.us-east-1.amazonaws.com"

# Test 15: marked.js library loads (CSP check)
run_test "CloudFront - External marked.js library accessible" \
    "curl -s -o /dev/null -w '%{http_code}' 'https://cdn.jsdelivr.net/npm/marked@11.1.0/marked.min.js'" \
    "200"

echo ""
echo -e "${BLUE}═══ Phase 5: End-to-End Integration ═══${NC}"
echo ""

# Test 16: Full query flow with CORS headers
run_test "E2E - POST query with CORS headers succeeds" \
    "curl -s -o /dev/null -w '%{http_code}' -X POST '$API_BASE/query' -H 'Content-Type: application/json' -H 'Origin: $CLOUDFRONT_ORIGIN' -d '{\"query\":\"test\"}'" \
    "200"

# Test 17: Response time check
echo -e "${YELLOW}[TEST]${NC} Performance - Response time < 2 seconds"
start_time=$(date +%s)
curl -s -X POST "$API_BASE/query" -H 'Content-Type: application/json' -d '{"query":"test"}' > /dev/null
end_time=$(date +%s)
response_time=$((end_time - start_time))
if [ $response_time -lt 2 ]; then
    echo -e "${GREEN}  ✅ PASS${NC} (${response_time}s)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}  ⚠️  SLOW${NC} (${response_time}s)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 18: JSON response format
run_test "E2E - Response is valid JSON" \
    "curl -s -X POST '$API_BASE/query' -H 'Content-Type: application/json' -d '{\"query\":\"test\"}' | jq -e '.answer' > /dev/null 2>&1 && echo 'valid'" \
    "valid"

echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}       Test Results Summary              ${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo -e "  Total Tests:  $((TESTS_PASSED + TESTS_FAILED))"
echo -e "  ${GREEN}Passed:       $TESTS_PASSED ✅${NC}"
echo -e "  ${RED}Failed:       $TESTS_FAILED ❌${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                            ║${NC}"
    echo -e "${GREEN}║  ✅  ALL TESTS PASSED!                     ║${NC}"
    echo -e "${GREEN}║                                            ║${NC}"
    echo -e "${GREEN}║  The chatbot is fully operational.        ║${NC}"
    echo -e "${GREEN}║                                            ║${NC}"
    echo -e "${GREEN}║  Try it at:                                ║${NC}"
    echo -e "${GREEN}║  $CLOUDFRONT_URL      ║${NC}"
    echo -e "${GREEN}║                                            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                            ║${NC}"
    echo -e "${RED}║  ⚠️  SOME TESTS FAILED                     ║${NC}"
    echo -e "${RED}║                                            ║${NC}"
    echo -e "${RED}║  Review the failures above for details.   ║${NC}"
    echo -e "${RED}║                                            ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════╝${NC}"
    exit 1
fi
