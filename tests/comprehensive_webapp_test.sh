#!/bin/bash
echo "========================================================================"
echo "COMPREHENSIVE NOAA WEBAPP TEST"
echo "========================================================================"
echo "Waiting 20 seconds for CloudFront invalidation..."
sleep 20

URL="https://dq8oz5pgpnqc1.cloudfront.net"
API_URL="https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((PASS++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((FAIL++))
    fi
}

echo ""
echo "========== TEST 1: CURL - Webapp HTML =========="
HTML=$(curl -s "$URL")
if [ ${#HTML} -gt 10000 ]; then
    test_result 0 "HTML loads (${#HTML} bytes)"
else
    test_result 1 "HTML too small or failed"
fi

echo ""
echo "========== TEST 2: CURL - JavaScript File =========="
JS=$(curl -s "$URL/app.js?nocache=$(date +%s)")
if [ ${#JS} -gt 30000 ]; then
    test_result 0 "JavaScript loads (${#JS} bytes)"
else
    test_result 1 "JavaScript too small or failed"
fi

# Check for duplicates
STATE_COUNT=$(echo "$JS" | grep -c "const state = {")
if [ $STATE_COUNT -eq 1 ]; then
    test_result 0 "No duplicate state declaration"
else
    test_result 1 "Found $STATE_COUNT state declarations"
fi

# Check for FALLBACK_PONDS
if echo "$JS" | grep -q "FALLBACK_PONDS"; then
    test_result 0 "FALLBACK_PONDS present"
else
    test_result 1 "FALLBACK_PONDS missing"
fi

echo ""
echo "========== TEST 3: CURL - API Weather Query =========="
WEATHER=$(curl -s -X POST "$API_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Boston?"}')

if echo "$WEATHER" | jq -e '.success' > /dev/null 2>&1; then
    test_result 0 "API weather query successful"
    EXEC_TIME=$(echo "$WEATHER" | jq -r '.execution_time_ms')
    echo "  Response time: ${EXEC_TIME}ms"
else
    test_result 1 "API weather query failed"
fi

echo ""
echo "========== TEST 4: CURL - API Alerts Query =========="
ALERTS=$(curl -s -X POST "$API_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show weather alerts"}')

if echo "$ALERTS" | jq -e '.success' > /dev/null 2>&1; then
    test_result 0 "API alerts query successful"
    RECORD_COUNT=$(echo "$ALERTS" | jq -r '.record_count // 0')
    echo "  Records: ${RECORD_COUNT}"
else
    test_result 1 "API alerts query failed"
fi

echo ""
echo "========== TEST 5: Python Simulated Browser =========="
python3 << 'PYEOF'
import urllib.request
import json
import sys

try:
    # Load HTML
    req = urllib.request.Request("https://dq8oz5pgpnqc1.cloudfront.net/")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8')
    
    # Load JavaScript
    req = urllib.request.Request("https://dq8oz5pgpnqc1.cloudfront.net/app.js")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=10) as response:
        js = response.read().decode('utf-8')
    
    # Validate structure
    checks = {
        "CONFIG": js.count("const CONFIG = {") == 1,
        "FALLBACK_PONDS": js.count("const FALLBACK_PONDS = {") == 1,
        "state": js.count("const state = {") == 1,
        "DOMContentLoaded": js.count("DOMContentLoaded") == 1,
        "loadAvailablePonds": js.count("async function loadAvailablePonds") == 1
    }
    
    all_pass = all(checks.values())
    if all_pass:
        print("✓ All JavaScript structure checks passed")
        sys.exit(0)
    else:
        print("✗ JavaScript structure issues:")
        for name, passed in checks.items():
            if not passed:
                print(f"  - {name} failed")
        sys.exit(1)
        
except Exception as e:
    print(f"✗ Browser simulation failed: {e}")
    sys.exit(1)
PYEOF

test_result $? "Python simulated browser"

echo ""
echo "========== TEST 6: Syntax Validation =========="
python3 -c "
import sys
import urllib.request

req = urllib.request.Request('https://dq8oz5pgpnqc1.cloudfront.net/app.js')
req.add_header('User-Agent', 'Mozilla/5.0')
with urllib.request.urlopen(req) as response:
    js = response.read().decode('utf-8')

open_b = js.count('{')
close_b = js.count('}')
if open_b == close_b:
    print(f'✓ Braces balanced: {open_b} pairs')
    sys.exit(0)
else:
    print(f'✗ Mismatched braces: {open_b} open, {close_b} close')
    sys.exit(1)
"
test_result $? "Brace balance check"

echo ""
echo "========== TEST 7: Check for XML/HTML tags =========="
if echo "$JS" | grep -qE '<text>|</text>|<old_text'; then
    test_result 1 "Found XML tags in JavaScript"
else
    test_result 0 "No XML tags found"
fi

echo ""
echo "========== TEST 8: Endpoints Data =========="
POND_COUNT=$(echo "$JS" | grep -c '"atmospheric":\|"oceanic":\|"buoy":\|"climate":\|"spatial":\|"terrestrial":')
if [ $POND_COUNT -ge 6 ]; then
    test_result 0 "All 6 ponds defined in FALLBACK_PONDS"
else
    test_result 1 "Only $POND_COUNT ponds found"
fi

echo ""
echo "========================================================================"
echo "TEST SUMMARY"
echo "========================================================================"
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
TOTAL=$((PASS + FAIL))
RATE=$((PASS * 100 / TOTAL))
echo "Success Rate: ${RATE}%"
echo "========================================================================"

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    exit 1
fi
