#!/bin/bash
#
# Deploy Enhanced NOAA Dashboard to S3 and CloudFront
# This script uploads the new live dashboard and invalidates the cache
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BUCKET_NAME="noaa-dashboard-${AWS_ACCOUNT_ID:-899626030376}"
REGION="us-east-1"
DASHBOARD_FILE="monitoring/dashboard_enhanced_live.html"

echo "=================================================="
echo "NOAA Enhanced Dashboard Deployment"
echo "=================================================="
echo ""

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓${NC} AWS Account: $ACCOUNT_ID"

# Check if we have the correct account
if [ "$ACCOUNT_ID" != "899626030376" ]; then
    echo -e "${RED}✗${NC} Wrong AWS account! Expected 899626030376, got $ACCOUNT_ID"
    exit 1
fi

# Check if dashboard file exists
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo -e "${RED}✗${NC} Dashboard file not found: $DASHBOARD_FILE"
    exit 1
fi

echo -e "${GREEN}✓${NC} Dashboard file found"
echo ""

# Try to find existing dashboard bucket
echo "Looking for existing S3 bucket..."
EXISTING_BUCKETS=$(aws s3 ls | grep -i dashboard | awk '{print $3}' || true)

if [ -n "$EXISTING_BUCKETS" ]; then
    echo -e "${GREEN}Found existing buckets:${NC}"
    echo "$EXISTING_BUCKETS"
    BUCKET_NAME=$(echo "$EXISTING_BUCKETS" | head -n1)
else
    # Create new bucket if needed
    BUCKET_NAME="noaa-dashboard-899626030376"
    echo -e "${YELLOW}No existing bucket found. Creating: $BUCKET_NAME${NC}"

    aws s3 mb s3://$BUCKET_NAME --region $REGION 2>/dev/null || true

    # Enable static website hosting
    aws s3 website s3://$BUCKET_NAME --index-document dashboard_enhanced_live.html

    # Set bucket policy for public read
    cat > /tmp/bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
        }
    ]
}
EOF

    aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file:///tmp/bucket-policy.json
    rm /tmp/bucket-policy.json
fi

echo -e "${GREEN}✓${NC} Using bucket: $BUCKET_NAME"
echo ""

# Upload dashboard files
echo "Uploading dashboard files..."

# Upload main dashboard
aws s3 cp "$DASHBOARD_FILE" s3://$BUCKET_NAME/dashboard_enhanced_live.html \
    --content-type "text/html" \
    --cache-control "max-age=300" \
    --acl public-read

echo -e "${GREEN}✓${NC} Uploaded dashboard_enhanced_live.html"

# Also upload as index.html for easy access
aws s3 cp "$DASHBOARD_FILE" s3://$BUCKET_NAME/index.html \
    --content-type "text/html" \
    --cache-control "max-age=300" \
    --acl public-read

echo -e "${GREEN}✓${NC} Uploaded index.html"

# Upload other dashboard files if they exist
if [ -f "monitoring/dashboard_comprehensive.html" ]; then
    aws s3 cp monitoring/dashboard_comprehensive.html s3://$BUCKET_NAME/dashboard_comprehensive.html \
        --content-type "text/html" \
        --cache-control "max-age=300" \
        --acl public-read
    echo -e "${GREEN}✓${NC} Uploaded dashboard_comprehensive.html"
fi

if [ -f "monitoring/dashboard-dynamic.js" ]; then
    aws s3 cp monitoring/dashboard-dynamic.js s3://$BUCKET_NAME/dashboard-dynamic.js \
        --content-type "application/javascript" \
        --cache-control "max-age=300" \
        --acl public-read
    echo -e "${GREEN}✓${NC} Uploaded dashboard-dynamic.js"
fi

if [ -f "monitoring/dashboard-modals.css" ]; then
    aws s3 cp monitoring/dashboard-modals.css s3://$BUCKET_NAME/dashboard-modals.css \
        --content-type "text/css" \
        --cache-control "max-age=300" \
        --acl public-read
    echo -e "${GREEN}✓${NC} Uploaded dashboard-modals.css"
fi

echo ""

# Get S3 website URL
S3_URL="http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
echo -e "${GREEN}✓${NC} S3 Website URL: $S3_URL"
echo ""

# Check for existing CloudFront distribution
echo "Checking for CloudFront distribution..."
DIST_ID=$(aws cloudfront list-distributions --output json | \
    python3 -c "import sys,json; dists=json.load(sys.stdin).get('DistributionList',{}).get('Items',[]); print(next((d['Id'] for d in dists if 'noaa' in d.get('Comment','').lower() or any('noaa' in o.get('DomainName','') for o in d['DistributionConfig']['Origins']['Items'])), ''))" 2>/dev/null || true)

if [ -n "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
    echo -e "${GREEN}✓${NC} Found existing CloudFront distribution: $DIST_ID"

    # Get CloudFront domain
    CF_DOMAIN=$(aws cloudfront get-distribution --id $DIST_ID --query 'Distribution.DomainName' --output text)
    echo -e "${GREEN}✓${NC} CloudFront Domain: https://$CF_DOMAIN"

    # Invalidate cache
    echo ""
    echo "Invalidating CloudFront cache..."
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id $DIST_ID \
        --paths "/*" \
        --query 'Invalidation.Id' \
        --output text)

    echo -e "${GREEN}✓${NC} Cache invalidation created: $INVALIDATION_ID"
    echo ""
    echo -e "${YELLOW}Note: Cache invalidation can take 5-15 minutes to complete${NC}"
else
    echo -e "${YELLOW}⚠${NC}  No CloudFront distribution found"
    echo ""
    echo "To create a CloudFront distribution, run:"
    echo ""
    echo "  aws cloudfront create-distribution --distribution-config file://cloudfront-config.json"
    echo ""
    echo "Or access directly via S3 website URL above"
fi

echo ""
echo "=================================================="
echo "DEPLOYMENT COMPLETE!"
echo "=================================================="
echo ""
echo "Dashboard URLs:"
echo "  Direct S3:        $S3_URL"
echo "  Enhanced:         $S3_URL/dashboard_enhanced_live.html"
echo ""

if [ -n "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
    echo "  CloudFront:       https://$CF_DOMAIN/dashboard_enhanced_live.html"
    echo "  (Wait 5-15 min for cache invalidation)"
fi

echo ""
echo "Test the dashboard:"
echo "  curl -I $S3_URL"
echo ""
echo "Key Features:"
echo "  ✓ Real-time data from AWS Lambda API"
echo "  ✓ Live radar and satellite imagery"
echo "  ✓ Interactive map with station locations"
echo "  ✓ Click any pond to view detailed metrics"
echo "  ✓ Auto-refresh every 60 seconds"
echo ""
