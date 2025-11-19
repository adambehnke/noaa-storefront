#!/bin/bash
# Quick Deployment Verification Script

echo "🔍 Verifying AI Multi-Pond System Deployment..."
echo ""

# 1. Check Lambda exists
echo "1. Checking Lambda function..."
if aws lambda get-function --function-name noaa-enhanced-handler-dev --region us-east-1 > /dev/null 2>&1; then
    echo "   ✅ Lambda exists: noaa-enhanced-handler-dev"
else
    echo "   ❌ Lambda not found"
    exit 1
fi

# 2. Check Lambda code version
echo "2. Checking Lambda code..."
LAST_MODIFIED=$(aws lambda get-function --function-name noaa-enhanced-handler-dev --region us-east-1 --query 'Configuration.LastModified' --output text)
echo "   Last updated: $LAST_MODIFIED"

# 3. Check recent logs
echo "3. Checking recent logs (last 5 min)..."
RECENT_LOGS=$(aws logs filter-log-events \
    --log-group-name "/aws/lambda/noaa-enhanced-handler-dev" \
    --start-time $(($(date +%s) * 1000 - 300000)) \
    --region us-east-1 \
    --limit 10 2>/dev/null | jq -r '.events[].message' 2>/dev/null | grep -i "processing query" | wc -l | xargs)

if [ "$RECENT_LOGS" -gt 0 ]; then
    echo "   ✅ Found $RECENT_LOGS recent queries"
else
    echo "   ⚠️  No recent queries (Lambda may not be receiving traffic)"
fi

# 4. Check for AI logs
echo "4. Checking for AI activity..."
AI_LOGS=$(aws logs filter-log-events \
    --log-group-name "/aws/lambda/noaa-enhanced-handler-dev" \
    --start-time $(($(date +%s) * 1000 - 3600000)) \
    --region us-east-1 \
    --filter-pattern "AI" \
    --limit 5 2>/dev/null | jq -r '.events[].message' 2>/dev/null | head -1)

if [ ! -z "$AI_LOGS" ]; then
    echo "   ✅ AI is active"
    echo "   Sample: $(echo "$AI_LOGS" | head -c 100)..."
else
    echo "   ⚠️  No AI activity detected (may need to test with a query)"
fi

# 5. Check Bedrock permissions
echo "5. Checking Bedrock permissions..."
ROLE_NAME=$(aws lambda get-function-configuration \
    --function-name noaa-enhanced-handler-dev \
    --region us-east-1 \
    --query 'Role' \
    --output text | awk -F'/' '{print $NF}')

if aws iam get-role-policy --role-name "$ROLE_NAME" --policy-name "BedrockAccess" > /dev/null 2>&1; then
    echo "   ✅ Bedrock permissions exist"
else
    echo "   ❌ Bedrock permissions missing"
    exit 1
fi

# 6. Check monitoring
echo "6. Checking monitoring..."
echo "   View logs: aws logs tail /aws/lambda/noaa-enhanced-handler-dev --follow"
echo "   Monitor:   ./test-scripts/monitor_system.sh"

echo ""
echo "🎉 Deployment verification complete!"
echo ""
echo "Next steps:"
echo "  1. Open your webapp"
echo "  2. Ask: 'Plan a maritime route from Boston to Portland'"
echo "  3. Verify it queries 3-4 ponds (not just 1)"
echo "  4. Check logs for 'AI selected X ponds'"
echo ""
