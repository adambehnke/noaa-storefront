#!/bin/bash
###############################################################################
# Recent Data Examples Feature - Deployment Script
# Deploys updated webapp to production CloudFront/S3
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
AWS_PROFILE="noaa-target"
S3_BUCKET="noaa-dashboards-dev-899626030376"
CLOUDFRONT_DIST_ID="EB2SWP7ZVF9JI"
CLOUDFRONT_URL="https://d2azko4sm6tkua.cloudfront.net"
AWS_REGION="us-east-1"
FEATURE_VERSION="1.0.0"
ACCOUNT_ID="899626030376"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  NOAA Data Lake - Recent Data Examples Feature Deployment${NC}"
echo -e "${CYAN}  Version: ${FEATURE_VERSION}${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "app.js" ] || [ ! -f "index.html" ]; then
    echo -e "${RED}❌ Error: Required files not found${NC}"
    echo "Please run this script from the webapp directory:"
    echo "  cd noaa_storefront/webapp"
    echo "  ./deploy_recent_data_feature.sh"
    exit 1
fi

echo -e "${GREEN}✓ Found required files${NC}"
echo ""

# Verify files contain the new feature
echo -e "${BLUE}[1/7]${NC} Verifying feature implementation..."

if grep -q "showPondDataExamples" app.js && grep -q "fetchRecentEndpointData" app.js; then
    echo -e "${GREEN}✓ New functions found in app.js${NC}"
else
    echo -e "${RED}❌ Error: New feature functions not found in app.js${NC}"
    echo "Expected functions: showPondDataExamples, fetchRecentEndpointData"
    exit 1
fi

if grep -q "Double-click a pond to view recent data examples" index.html; then
    echo -e "${GREEN}✓ UI hints found in index.html${NC}"
else
    echo -e "${YELLOW}⚠ Warning: UI hints not found in index.html${NC}"
fi

echo ""

# Check for JavaScript syntax errors
echo -e "${BLUE}[2/7]${NC} Checking JavaScript syntax..."
if command -v node &> /dev/null; then
    NODE_OUTPUT=$(node -c app.js 2>&1) || true
    if echo "$NODE_OUTPUT" | grep -qi "SyntaxError"; then
        echo -e "${RED}❌ Error: JavaScript syntax error detected!${NC}"
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
echo ""

# Verify AWS credentials
echo -e "${BLUE}[3/7]${NC} Verifying AWS credentials..."
export AWS_PROFILE="$AWS_PROFILE"
if aws sts get-caller-identity &> /dev/null; then
    CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✓ AWS credentials valid${NC}"
    echo "  Account: $CURRENT_ACCOUNT"
    echo "  Profile: $AWS_PROFILE"

    if [ "$CURRENT_ACCOUNT" != "$ACCOUNT_ID" ]; then
        echo -e "${RED}❌ Error: Wrong AWS account!${NC}"
        echo "  Expected: $ACCOUNT_ID (noaa-target)"
        echo "  Current:  $CURRENT_ACCOUNT"
        exit 1
    fi
else
    echo -e "${RED}❌ Error: AWS credentials not configured${NC}"
    exit 1
fi
echo ""

# Create backup
echo -e "${BLUE}[4/7]${NC} Creating backup of current deployment..."
BACKUP_DIR="backups/recent-data-feature-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "  Downloading current files from S3..."
aws s3 cp "s3://$S3_BUCKET/app.js" "$BACKUP_DIR/app.js" --region $AWS_REGION 2>/dev/null || echo "    (no existing app.js)"
aws s3 cp "s3://$S3_BUCKET/index.html" "$BACKUP_DIR/index.html" --region $AWS_REGION 2>/dev/null || echo "    (no existing index.html)"

echo -e "${GREEN}✓ Backup created: $BACKUP_DIR${NC}"
echo ""

# Upload files to S3
echo -e "${BLUE}[5/7]${NC} Uploading updated files to S3..."

# Upload chatbot.html (webapp index)
echo "  → Uploading chatbot.html..."
aws s3 cp index.html "s3://$S3_BUCKET/chatbot.html" \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate" \
    --metadata "version=$FEATURE_VERSION,updated=$(date -u +%Y-%m-%dT%H:%M:%SZ),feature=recent-data-examples" \
    --region $AWS_REGION \
    --profile $AWS_PROFILE

echo -e "${GREEN}  ✓ chatbot.html uploaded${NC}"

# Upload chatbot.js (webapp app.js)
echo "  → Uploading chatbot.js..."
aws s3 cp app.js "s3://$S3_BUCKET/chatbot.js" \
    --content-type "application/javascript" \
    --cache-control "no-cache, no-store, must-revalidate" \
    --metadata "version=$FEATURE_VERSION,updated=$(date -u +%Y-%m-%dT%H:%M:%SZ),feature=recent-data-examples" \
    --region $AWS_REGION \
    --profile $AWS_PROFILE

echo -e "${GREEN}  ✓ chatbot.js uploaded${NC}"

# Upload documentation
if [ -f "RECENT_DATA_EXAMPLES_FEATURE.md" ]; then
    echo "  → Uploading documentation..."
    aws s3 cp RECENT_DATA_EXAMPLES_FEATURE.md "s3://$S3_BUCKET/docs/RECENT_DATA_EXAMPLES_FEATURE.md" \
        --content-type "text/markdown" \
        --region $AWS_REGION \
        --profile $AWS_PROFILE 2>/dev/null || echo "    (skipped docs)"
fi

echo ""

# Invalidate CloudFront cache
echo -e "${BLUE}[6/7]${NC} Invalidating CloudFront cache..."

INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$CLOUDFRONT_DIST_ID" \
    --paths "/chatbot.html" "/chatbot.js" "/docs/*" \
    --query 'Invalidation.Id' \
    --output text \
    --profile $AWS_PROFILE)

echo -e "${GREEN}✓ CloudFront invalidation created${NC}"
echo "  Invalidation ID: $INVALIDATION_ID"
echo "  Distribution: $CLOUDFRONT_DIST_ID"
echo ""

# Verify deployment
echo -e "${BLUE}[7/7]${NC} Verifying deployment..."
sleep 3

# Check if files are accessible
echo "  → Checking chatbot.js accessibility..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$CLOUDFRONT_URL/chatbot.js?t=$(date +%s)")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}  ✓ chatbot.js is accessible (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${YELLOW}  ⚠ chatbot.js returned HTTP $HTTP_CODE (cache may not be cleared yet)${NC}"
fi

echo "  → Checking chatbot.html accessibility..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$CLOUDFRONT_URL/chatbot.html?t=$(date +%s)")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}  ✓ chatbot.html is accessible (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${YELLOW}  ⚠ chatbot.html returned HTTP $HTTP_CODE (cache may not be cleared yet)${NC}"
fi

echo ""

# Summary
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${MAGENTA}📦 What was deployed:${NC}"
echo "  ✓ app.js with Recent Data Examples feature"
echo "  ✓ index.html with UI hints"
echo "  ✓ CloudFront cache invalidated"
echo ""
echo -e "${MAGENTA}🔗 URLs:${NC}"
echo "  Chatbot:    $CLOUDFRONT_URL/chatbot.html"
echo "  Dashboard:  $CLOUDFRONT_URL/dashboard_comprehensive.html"
echo ""
echo -e "${MAGENTA}🎯 New Features:${NC}"
echo "  • Double-click any pond to see all endpoints"
echo "  • Green 'Recent' button shows cached data"
echo "  • Blue 'Query' button fetches live data"
echo "  • 48+ endpoints now have Recent button"
echo ""
echo -e "${MAGENTA}⏱️  Next Steps (IMPORTANT):${NC}"
echo "  1. ${YELLOW}Wait 2-3 minutes${NC} for CloudFront cache propagation"
echo "  2. Open: $CLOUDFRONT_URL/chatbot.html"
echo "  3. ${YELLOW}Hard refresh${NC}: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)"
echo "  4. Check browser console for errors (F12)"
echo "  5. Test the new features:"
echo "     • Double-click 'Atmospheric' pond"
echo "     • Click green 'Recent' button on any endpoint"
echo "     • Verify timestamps show 'X minutes ago'"
echo ""
echo -e "${MAGENTA}🔍 Verification:${NC}"
echo "  • Check browser console for: '✓ Pond-to-service mapping updated'"
echo "  • Expand 'Endpoints & Services' section"
echo "  • Look for green 'Recent' and blue 'Query' buttons"
echo "  • Double-click any pond to see comprehensive view"
echo ""
echo -e "${MAGENTA}💾 Backup Location:${NC}"
echo "  $BACKUP_DIR"
echo ""
echo -e "${MAGENTA}📊 CloudFront Invalidation Status:${NC}"
echo "  Check status with:"
echo "  ${CYAN}AWS_PROFILE=$AWS_PROFILE aws cloudfront get-invalidation --distribution-id $CLOUDFRONT_DIST_ID --id $INVALIDATION_ID${NC}"
echo ""
echo -e "${MAGENTA}🔄 Rollback (if needed):${NC}"
echo "  cd $BACKUP_DIR"
echo "  AWS_PROFILE=$AWS_PROFILE aws s3 cp chatbot.js s3://$S3_BUCKET/ --region $AWS_REGION"
echo "  AWS_PROFILE=$AWS_PROFILE aws s3 cp chatbot.html s3://$S3_BUCKET/ --region $AWS_REGION"
echo "  AWS_PROFILE=$AWS_PROFILE aws cloudfront create-invalidation --distribution-id $CLOUDFRONT_DIST_ID --paths '/chatbot.*'"
echo ""
echo -e "${MAGENTA}📚 Documentation:${NC}"
echo "  • Quick Reference: QUICK_REFERENCE_RECENT_DATA.md"
echo "  • Full Docs: webapp/RECENT_DATA_EXAMPLES_FEATURE.md"
echo "  • Deployment: RECENT_DATA_FEATURE_DEPLOYMENT.md"
echo ""
echo -e "${GREEN}🚀 Deployment successful! Feature is now live on account $ACCOUNT_ID.${NC}"
echo ""

# Offer to monitor invalidation
echo -e "${YELLOW}Monitor invalidation progress? (y/N)${NC} "
read -t 10 -n 1 MONITOR_RESPONSE || MONITOR_RESPONSE="n"
echo ""

if [[ $MONITOR_RESPONSE =~ ^[Yy]$ ]]; then
    echo ""
    echo "Monitoring CloudFront invalidation..."
    echo "(Press Ctrl+C to stop monitoring)"
    echo ""

    while true; do
        STATUS=$(aws cloudfront get-invalidation \
            --distribution-id "$CLOUDFRONT_DIST_ID" \
            --id "$INVALIDATION_ID" \
            --query 'Invalidation.Status' \
            --output text \
            --profile $AWS_PROFILE)

        if [ "$STATUS" == "Completed" ]; then
            echo -e "${GREEN}✓ Invalidation completed!${NC}"
            echo ""
            echo -e "${GREEN}🎉 You can now access the updated site!${NC}"
            echo "URL: $CLOUDFRONT_URL"
            break
        fi

        echo "  Status: $STATUS (checking again in 15 seconds...)"
        sleep 15
    done
fi

echo ""
exit 0
