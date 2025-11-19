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
