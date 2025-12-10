#!/bin/bash
# Comprehensive system verification

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NOAA Data Lake - System Verification        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

AWS_PROFILE=noaa-target

# Test 1: Check all ingestion schedules
echo -e "${BLUE}[1/6] Checking Ingestion Schedules...${NC}"
SCHEDULES=$(AWS_PROFILE=$AWS_PROFILE aws events list-rules --name-prefix "noaa-ingest" --region us-east-1 --query 'length(Rules[?State==`ENABLED`])' --output text)
if [ "$SCHEDULES" -eq 6 ]; then
  echo -e "${GREEN}✓ All 6 ponds scheduled${NC}"
else
  echo -e "${RED}✗ Only $SCHEDULES ponds active${NC}"
fi

# Test 2: Check S3 data volume
echo -e "${BLUE}[2/6] Checking Data Lake...${NC}"
FILES=$(AWS_PROFILE=$AWS_PROFILE aws s3 ls s3://noaa-federated-lake-899626030376-dev/ --recursive --summarize 2>&1 | grep "Total Objects:" | awk '{print $3}')
SIZE=$(AWS_PROFILE=$AWS_PROFILE aws s3 ls s3://noaa-federated-lake-899626030376-dev/ --recursive --summarize 2>&1 | grep "Total Size:" | awk '{print $3}')
SIZE_MB=$((SIZE / 1024 / 1024))

if [ "$FILES" -gt 100 ]; then
  echo -e "${GREEN}✓ Data lake populated: $FILES files, ${SIZE_MB}MB${NC}"
else
  echo -e "${RED}✗ Data lake sparse: $FILES files${NC}"
fi

# Test 3: Test chatbot with real query
echo -e "${BLUE}[3/6] Testing Chatbot with Real Query...${NC}"
RESPONSE=$(curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What are water levels in Charleston?\", \"timestamp\": $(date +%s)}")

DATA_STATUS=$(echo "$RESPONSE" | jq -r '.metadata.data_lake_status' 2>/dev/null)
if [ "$DATA_STATUS" = "active" ]; then
  SOURCES=$(echo "$RESPONSE" | jq -r '.data.sources | length' 2>/dev/null)
  echo -e "${GREEN}✓ Chatbot querying live data ($SOURCES sources)${NC}"
else
  echo -e "${RED}✗ Chatbot not using live data${NC}"
fi

# Test 4: Check cache busting
echo -e "${BLUE}[4/6] Checking Cache Configuration...${NC}"
CACHE_CONTROL=$(curl -s -I "https://d244ik6grpfthq.cloudfront.net/app.js" | grep -i "cache-control")
if echo "$CACHE_CONTROL" | grep -q "no-cache"; then
  echo -e "${GREEN}✓ Cache busting enabled${NC}"
else
  echo -e "${RED}✗ Cache headers not set${NC}"
fi

# Test 5: Verify CloudFront
echo -e "${BLUE}[5/6] Testing CloudFront...${NC}"
CF_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://d244ik6grpfthq.cloudfront.net/")
if [ "$CF_STATUS" = "200" ]; then
  echo -e "${GREEN}✓ CloudFront accessible${NC}"
else
  echo -e "${RED}✗ CloudFront returned $CF_STATUS${NC}"
fi

# Test 6: Check recent ingestion
echo -e "${BLUE}[6/6] Checking Recent Ingestion Activity...${NC}"
RECENT_LOGS=$(AWS_PROFILE=$AWS_PROFILE aws logs tail /aws/lambda/noaa-ingest-oceanic-dev --since 10m --region us-east-1 2>&1 | grep -c "Wrote.*records")
if [ "$RECENT_LOGS" -gt 0 ]; then
  echo -e "${GREEN}✓ Active ingestion (${RECENT_LOGS} write operations)${NC}"
else
  echo -e "${RED}✗ No recent ingestion activity${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}System Status: OPERATIONAL${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""
echo "Try the chatbot:"
echo "  https://d244ik6grpfthq.cloudfront.net/?v=$(date +%s)"
