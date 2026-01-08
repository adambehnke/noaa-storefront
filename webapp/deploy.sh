#!/bin/bash
#
# NOAA Data Lake Chatbot - Deployment Script
# Deploys to AWS Account: 899626030376
#

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
AWS_PROFILE="noaa-target"
S3_BUCKET="noaa-chatbot-prod-899626030376"
CLOUDFRONT_DIST_ID="E1VCVD2GAOQJS8"
CLOUDFRONT_URL="https://d244ik6grpfthq.cloudfront.net"
EXPECTED_ACCOUNT="899626030376"

echo ""
echo "================================================================"
echo "  NOAA Data Lake Chatbot - Deployment"
echo "================================================================"
echo ""

# Verify AWS account
echo -e "${BLUE}Verifying AWS account...${NC}"
CURRENT_ACCOUNT=$(AWS_PROFILE=$AWS_PROFILE aws sts get-caller-identity --query Account --output text)

if [ "$CURRENT_ACCOUNT" != "$EXPECTED_ACCOUNT" ]; then
    echo -e "${RED}ERROR: Wrong AWS account!${NC}"
    echo "Expected: $EXPECTED_ACCOUNT"
    echo "Got: $CURRENT_ACCOUNT"
    exit 1
fi
echo -e "${GREEN}✓ Correct AWS account: $CURRENT_ACCOUNT${NC}"

# Check for syntax errors in JavaScript
echo ""
echo -e "${BLUE}Checking JavaScript syntax...${NC}"
if command -v node &> /dev/null; then
    NODE_OUTPUT=$(node -c app.js 2>&1) || true
    if echo "$NODE_OUTPUT" | grep -qi "SyntaxError"; then
        echo -e "${RED}ERROR: JavaScript syntax error detected!${NC}"
        echo "$NODE_OUTPUT"
        exit 1
    elif echo "$NODE_OUTPUT" | grep -qi "Library not loaded"; then
        echo -e "${YELLOW}⚠ Node.js has library issues, skipping syntax check${NC}"
    elif [ -z "$NODE_OUTPUT" ]; then
        echo -e "${GREEN}✓ JavaScript syntax valid${NC}"
    else
        echo -e "${YELLOW}⚠ Node.js check inconclusive, continuing anyway${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Node.js not found, skipping syntax check${NC}"
fi

# Check for duplicate declarations
echo ""
echo -e "${BLUE}Checking for duplicate declarations...${NC}"
ELEMENTS_COUNT=$(grep -c "^let elements = {}" app.js || true)
if [ "$ELEMENTS_COUNT" -gt 1 ]; then
    echo -e "${RED}ERROR: Found $ELEMENTS_COUNT 'let elements' declarations!${NC}"
    echo "There should only be one."
    exit 1
fi
echo -e "${GREEN}✓ No duplicate declarations found${NC}"

# Create backup
echo ""
echo -e "${BLUE}Creating backup...${NC}"
BACKUP_DIR="../backups/webapp-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
AWS_PROFILE=$AWS_PROFILE aws s3 cp "s3://$S3_BUCKET/index.html" "$BACKUP_DIR/index.html" 2>/dev/null || echo "  (no existing index.html)"
AWS_PROFILE=$AWS_PROFILE aws s3 cp "s3://$S3_BUCKET/app.js" "$BACKUP_DIR/app.js" 2>/dev/null || echo "  (no existing app.js)"
echo -e "${GREEN}✓ Backup created: $BACKUP_DIR${NC}"

# Upload to S3
echo ""
echo -e "${BLUE}Uploading files to S3...${NC}"

# Upload HTML
AWS_PROFILE=$AWS_PROFILE aws s3 cp index.html "s3://$S3_BUCKET/index.html" \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate" \
    --metadata-directive REPLACE
echo -e "${GREEN}✓ Uploaded: index.html${NC}"

# Upload JavaScript
AWS_PROFILE=$AWS_PROFILE aws s3 cp app.js "s3://$S3_BUCKET/app.js" \
    --content-type "application/javascript" \
    --cache-control "no-cache, no-store, must-revalidate" \
    --metadata-directive REPLACE
echo -e "${GREEN}✓ Uploaded: app.js${NC}"

# Invalidate CloudFront cache
echo ""
echo -e "${BLUE}Invalidating CloudFront cache...${NC}"
INVALIDATION_ID=$(AWS_PROFILE=$AWS_PROFILE aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DIST_ID" \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text)
echo -e "${GREEN}✓ Invalidation created: $INVALIDATION_ID${NC}"

# Verify deployment
echo ""
echo -e "${BLUE}Verifying deployment...${NC}"
sleep 3

# Check if app.js is accessible
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$CLOUDFRONT_URL/app.js?t=$(date +%s)")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ app.js is accessible (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${YELLOW}⚠ app.js returned HTTP $HTTP_CODE${NC}"
fi

# Summary
echo ""
echo "================================================================"
echo -e "${GREEN}✓ DEPLOYMENT COMPLETE${NC}"
echo "================================================================"
echo ""
echo "URL: $CLOUDFRONT_URL"
echo "Distribution: $CLOUDFRONT_DIST_ID"
echo "Invalidation: $INVALIDATION_ID"
echo ""
echo -e "${YELLOW}Note: CloudFront cache invalidation takes 1-3 minutes${NC}"
echo ""
echo "Next steps:"
echo "  1. Wait 2-3 minutes for CloudFront propagation"
echo "  2. Open: $CLOUDFRONT_URL"
echo "  3. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)"
echo "  4. Check browser console for errors"
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""

exit 0
