#!/bin/bash
# Update dashboard with fresh pond data

set -e

echo "🔄 Updating dashboard with fresh data..."

# Generate fresh metadata
echo "1. Generating fresh pond metadata..."
cd ../scripts
python3 generate_pond_metadata.py

# Deploy metadata
echo "2. Deploying metadata to S3..."
cd ..
export AWS_PROFILE=noaa-target
aws s3 cp webapp/pond_metadata.json s3://noaa-dashboards-dev-899626030376/pond_metadata.json --content-type "application/json"

# Update chatbot to have fixed script reference
echo "3. Deploying updated chatbot..."
aws s3 cp webapp/index.html s3://noaa-dashboards-dev-899626030376/chatbot.html --content-type "text/html" --cache-control "no-cache"

# Invalidate CloudFront
echo "4. Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id EB2SWP7ZVF9JI --paths "/pond_metadata.json" "/chatbot.html"

echo ""
echo "✅ Dashboard updated!"
echo "📊 Latest data is now available at:"
echo "   https://d2azko4sm6tkua.cloudfront.net/chatbot.html"
echo ""
echo "⏱️  Wait 2-3 minutes for CloudFront cache to clear"
