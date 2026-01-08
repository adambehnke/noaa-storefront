#!/bin/bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ENV="dev"

echo "=== NOAA FEDERATED DATA LAKE - QUICK STATUS ==="
echo ""
echo "Account ID: $ACCOUNT_ID"
echo "Environment: $ENV"
echo ""

echo "📦 S3 Buckets:"
aws s3 ls | grep noaa | awk '{print "  - " $3}'

echo ""
echo "⚡ Lambda Functions:"
LAMBDA_COUNT=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' --output text | wc -w)
echo "  Total: $LAMBDA_COUNT"
if [ "$LAMBDA_COUNT" -eq 0 ]; then
    echo "  ⚠️  NO LAMBDA FUNCTIONS DEPLOYED"
fi

echo ""
echo "⏰ EventBridge Rules:"
RULE_COUNT=$(aws events list-rules --query 'Rules[?contains(Name, `noaa`)].Name' --output text | wc -w)
echo "  Total: $RULE_COUNT ($(aws events list-rules --query 'Rules[?contains(Name, `noaa`) && State==`ENABLED`].Name' --output text | wc -w) enabled)"

echo ""
echo "🗄️  Athena Databases:"
aws athena list-databases --catalog-name AwsDataCatalog --query 'DatabaseList[?contains(Name, `noaa`)].Name' --output text | tr '\t' '\n' | sed 's/^/  - /'

echo ""
echo "📊 Recent Data (last 24h):"
if aws s3 ls s3://noaa-federated-lake-${ACCOUNT_ID}-${ENV}/bronze/atmospheric/ --recursive 2>/dev/null | tail -1 | grep -q "$(date +%Y-%m-%d)"; then
    echo "  ✅ Data ingested today"
else
    LAST_FILE=$(aws s3 ls s3://noaa-federated-lake-${ACCOUNT_ID}-${ENV}/bronze/atmospheric/ --recursive 2>/dev/null | tail -1)
    if [ -n "$LAST_FILE" ]; then
        echo "  ⚠️  Last ingestion: $(echo $LAST_FILE | awk '{print $1, $2}')"
    else
        echo "  ❌ No data found"
    fi
fi

echo ""
echo "=== SYSTEM STATUS ==="
if [ "$LAMBDA_COUNT" -eq 0 ]; then
    echo "❌ SYSTEM NOT OPERATIONAL - Lambda functions need deployment"
    echo ""
    echo "Next steps:"
    echo "  1. Run: ./scripts/migrate_to_new_account.sh --env dev"
    echo "  2. Or: ./scripts/deploy_to_aws.sh --env dev"
else
    echo "✅ SYSTEM OPERATIONAL"
fi
echo ""
