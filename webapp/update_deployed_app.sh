#!/bin/bash
###############################################################################
# Quick Update Script for Deployed NOAA Webapp
# Updates app.js on S3 and invalidates CloudFront cache
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
STACK_NAME="noaa-chatbot"
ENVIRONMENT="prod"
AWS_REGION="us-east-1"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  NOAA Webapp Quick Update - Deploy app.js to CloudFront${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "app.js" ]; then
    echo -e "${RED}Error: app.js not found in current directory${NC}"
    echo "Please run this script from the webapp directory:"
    echo "  cd noaa_storefront/webapp"
    echo "  ./update_deployed_app.sh"
    exit 1
fi

# Get stack outputs
echo -e "${BLUE}[1/5]${NC} Fetching CloudFormation stack information..."

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" == "None" ]; then
    echo -e "${RED}Error: Could not find S3 bucket in CloudFormation stack${NC}"
    echo "Stack name: $STACK_NAME-$ENVIRONMENT"
    echo ""
    echo "Available stacks:"
    aws cloudformation list-stacks --region $AWS_REGION --query 'StackSummaries[?StackStatus==`CREATE_COMPLETE` || StackStatus==`UPDATE_COMPLETE`].StackName' --output table
    exit 1
fi

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text 2>/dev/null)

WEBSITE_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
    --output text 2>/dev/null)

echo -e "${GREEN}✓ Found deployment resources:${NC}"
echo "  S3 Bucket: $BUCKET_NAME"
echo "  CloudFront ID: $DISTRIBUTION_ID"
echo "  Website URL: $WEBSITE_URL"
echo ""

# Backup current app.js from S3
echo -e "${BLUE}[2/5]${NC} Creating backup of current app.js..."
BACKUP_FILE="app.js.backup.$(date +%Y%m%d_%H%M%S)"
aws s3 cp "s3://$BUCKET_NAME/app.js" "$BACKUP_FILE" --region $AWS_REGION 2>/dev/null || echo "  (No existing file to backup)"
echo -e "${GREEN}✓ Backup saved as: $BACKUP_FILE${NC}"
echo ""

# Upload new app.js
echo -e "${BLUE}[3/5]${NC} Uploading updated app.js to S3..."
aws s3 cp app.js "s3://$BUCKET_NAME/" \
    --content-type "application/javascript" \
    --cache-control "public, max-age=300" \
    --metadata "updated=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --region $AWS_REGION

echo -e "${GREEN}✓ app.js uploaded successfully${NC}"
echo ""

# Also upload index.html to ensure compatibility
echo -e "${BLUE}[4/5]${NC} Uploading index.html (for compatibility)..."
if [ -f "index.html" ]; then
    aws s3 cp index.html "s3://$BUCKET_NAME/" \
        --content-type "text/html" \
        --cache-control "no-cache, no-store, must-revalidate" \
        --region $AWS_REGION
    echo -e "${GREEN}✓ index.html uploaded${NC}"
else
    echo -e "${YELLOW}⚠ index.html not found, skipping${NC}"
fi
echo ""

# Invalidate CloudFront cache
if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
    echo -e "${BLUE}[5/5]${NC} Invalidating CloudFront cache..."

    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/app.js" "/index.html" "/" \
        --query 'Invalidation.Id' \
        --output text)

    echo -e "${GREEN}✓ CloudFront invalidation created: $INVALIDATION_ID${NC}"
    echo ""
    echo -e "${YELLOW}Note: Cache invalidation can take 5-15 minutes to complete${NC}"
    echo ""

    # Show invalidation status
    echo "Checking invalidation status..."
    STATUS=$(aws cloudfront get-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --id "$INVALIDATION_ID" \
        --query 'Invalidation.Status' \
        --output text)
    echo "  Status: $STATUS"
else
    echo -e "${YELLOW}[5/5] No CloudFront distribution found, skipping cache invalidation${NC}"
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}What was updated:${NC}"
echo "  ✓ app.js with fallback endpoint data"
echo "  ✓ CloudFront cache invalidated"
echo ""
echo -e "${BLUE}How to verify:${NC}"
echo "  1. Wait 5-15 minutes for cache invalidation"
echo "  2. Open website in incognito mode: $WEBSITE_URL"
echo "  3. Force refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)"
echo "  4. Check browser console for: '✓ Using 6 data ponds'"
echo "  5. Click 'Endpoints & Services' - should show 40+ endpoints"
echo "  6. Click 'Service Status' - should show 6 active services"
echo ""
echo -e "${BLUE}Troubleshooting:${NC}"
echo "  • If still shows 'Loading...', wait a few more minutes"
echo "  • Clear browser cache completely"
echo "  • Check CloudFront invalidation status:"
echo "    aws cloudfront get-invalidation --distribution-id $DISTRIBUTION_ID --id $INVALIDATION_ID"
echo ""
echo -e "${BLUE}Backup location:${NC}"
echo "  $BACKUP_FILE"
echo ""

# Offer to wait for invalidation
if [ -n "$DISTRIBUTION_ID" ] && [ "$DISTRIBUTION_ID" != "None" ]; then
    echo -e "${YELLOW}Do you want to wait for invalidation to complete? (y/N)${NC}"
    read -t 10 -n 1 WAIT_RESPONSE || WAIT_RESPONSE="n"
    echo ""

    if [[ $WAIT_RESPONSE =~ ^[Yy]$ ]]; then
        echo "Waiting for invalidation to complete..."
        while true; do
            STATUS=$(aws cloudfront get-invalidation \
                --distribution-id "$DISTRIBUTION_ID" \
                --id "$INVALIDATION_ID" \
                --query 'Invalidation.Status' \
                --output text)

            if [ "$STATUS" == "Completed" ]; then
                echo -e "${GREEN}✓ Invalidation completed!${NC}"
                echo "You can now access the updated site at: $WEBSITE_URL"
                break
            fi

            echo "  Status: $STATUS (checking again in 30 seconds...)"
            sleep 30
        done
    fi
fi

echo ""
echo -e "${GREEN}🚀 Update deployed successfully!${NC}"
echo ""
