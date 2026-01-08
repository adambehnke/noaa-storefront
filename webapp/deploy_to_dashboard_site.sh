#!/bin/bash
# Deploy webapp to the live dashboard site
# This deploys the chatbot webapp alongside the dashboards

set -e

BUCKET="noaa-dashboard-hosting-dev-dashboardbucket-i25hbvplc88p"
REGION="us-east-1"
CLOUDFRONT="E3KTQM89V9THUI"

echo "🚀 Deploying NOAA Chatbot Webapp with Recent Data Feature..."
echo ""

# Create backup
echo "📦 Creating backup..."
mkdir -p backups/deploy-$(date +%Y%m%d-%H%M%S)
aws s3 cp s3://$BUCKET/chatbot.html backups/deploy-$(date +%Y%m%d-%H%M%S)/ 2>/dev/null || echo "  (no existing chatbot.html)"
aws s3 cp s3://$BUCKET/chatbot.js backups/deploy-$(date +%Y%m%d-%H%M%S)/ 2>/dev/null || echo "  (no existing chatbot.js)"

# Deploy files
echo ""
echo "📤 Uploading files..."
aws s3 cp index.html s3://$BUCKET/chatbot.html --content-type "text/html" --cache-control "no-cache" --region $REGION
aws s3 cp app.js s3://$BUCKET/chatbot.js --content-type "application/javascript" --cache-control "no-cache" --region $REGION

# Invalidate cache
echo ""
echo "🔄 Invalidating CloudFront cache..."
aws cloudfront create-invalidation --distribution-id $CLOUDFRONT --paths "/chatbot.html" "/chatbot.js" --region $REGION

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Access your chatbot at:"
echo "   https://d2azko4sm6tkua.cloudfront.net/chatbot.html"
echo ""
echo "⏱️  Wait 2-3 minutes for CloudFront cache to clear"
echo ""
