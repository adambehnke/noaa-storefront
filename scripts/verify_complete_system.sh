#!/bin/bash

source config/environment.sh

echo "================================================================"
echo "NOAA FEDERATED DATA LAKE - COMPLETE SYSTEM VERIFICATION"
echo "================================================================"
echo ""
echo "Account: $AWS_ACCOUNT_ID"
echo "Date: $(date)"
echo ""

# 1. Check all ponds for data
echo "1. VERIFYING DATA INGESTION ACROSS ALL PONDS"
echo "=============================================="
for pond in atmospheric oceanic buoy climate terrestrial spatial; do
    printf "%-15s: " "$pond"
    count=$(aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/${pond}/ --recursive 2>/dev/null | wc -l)
    latest=$(aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/${pond}/ --recursive 2>/dev/null | tail -1 | awk '{print $1, $2}')
    printf "%6d files | Latest: %s\n" "$count" "$latest"
done
echo ""

# 2. Check Gold layer transformation
echo "2. VERIFYING MEDALLION LAYER (Bronze → Gold)"
echo "=============================================="
for pond in atmospheric oceanic buoy climate terrestrial spatial; do
    bronze_count=$(aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/${pond}/ --recursive 2>/dev/null | wc -l)
    gold_count=$(aws s3 ls s3://${DATA_LAKE_BUCKET}/gold/${pond}/ --recursive 2>/dev/null | wc -l)
    printf "%-15s: Bronze: %6d → Gold: %6d\n" "$pond" "$bronze_count" "$gold_count"
done
echo ""

# 3. Check Glue Crawlers
echo "3. VERIFYING GLUE CRAWLERS"
echo "=========================="
crawler_count=$(aws glue list-crawlers --query 'CrawlerNames' --output text | wc -w)
echo "Total Crawlers: $crawler_count"
aws glue get-crawlers --query 'Crawlers[?contains(Name, `noaa`)].{Name:Name,State:State,Tables:LastCrawl.TablesCreated}' --output table | head -20
echo ""

# 4. Check Athena Databases and Tables
echo "4. VERIFYING ATHENA QUERY CAPABILITY"
echo "====================================="
echo "Databases:"
aws athena list-databases --catalog-name AwsDataCatalog --query 'DatabaseList[?contains(Name, `noaa`)].Name' --output table
echo ""

echo "Bronze Tables:"
aws athena list-table-metadata --catalog-name AwsDataCatalog --database-name noaa_bronze_dev --query 'TableMetadataList[0:5].Name' --output table 2>/dev/null
echo ""

echo "Gold Tables:"
aws athena list-table-metadata --catalog-name AwsDataCatalog --database-name noaa_gold_dev --query 'TableMetadataList[0:5].Name' --output table 2>/dev/null
echo ""

# 5. Test Query Execution
echo "5. TESTING ATHENA FEDERATED QUERIES"
echo "===================================="

# Create a simple test query
TEST_QUERY="SELECT COUNT(*) as total_files FROM noaa_bronze_dev.atmospheric LIMIT 10"

echo "Executing test query..."
QUERY_ID=$(aws athena start-query-execution \
  --query-string "$TEST_QUERY" \
  --result-configuration "OutputLocation=s3://${ATHENA_RESULTS_BUCKET}/" \
  --query-execution-context "Database=noaa_bronze_dev" \
  --query 'QueryExecutionId' \
  --output text 2>/dev/null)

if [ -n "$QUERY_ID" ]; then
    echo "Query ID: $QUERY_ID"
    sleep 3
    
    STATUS=$(aws athena get-query-execution --query-execution-id $QUERY_ID --query 'QueryExecution.Status.State' --output text 2>/dev/null)
    echo "Query Status: $STATUS"
    
    if [ "$STATUS" = "SUCCEEDED" ]; then
        echo "✓ Athena queries working!"
    else
        echo "⚠ Query status: $STATUS"
    fi
else
    echo "⚠ Unable to execute test query (tables may still be creating)"
fi
echo ""

# 6. Check CloudWatch Dashboard
echo "6. VERIFYING CLOUDWATCH MONITORING"
echo "=================================="
DASHBOARD=$(aws cloudwatch list-dashboards --query 'DashboardEntries[?contains(DashboardName, `NOAA`)].DashboardName' --output text)
if [ -n "$DASHBOARD" ]; then
    echo "✓ Dashboard exists: $DASHBOARD"
    echo "  URL: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=$DASHBOARD"
else
    echo "⚠ No dashboard found"
fi
echo ""

# 7. Check Data Quality Lambda
echo "7. VERIFYING DATA QUALITY LAMBDA"
echo "================================"
DQ_LAMBDA=$(aws lambda get-function --function-name noaa-data-quality-dev --query 'Configuration.FunctionName' --output text 2>/dev/null)
if [ "$DQ_LAMBDA" = "noaa-data-quality-dev" ]; then
    echo "✓ Data Quality Lambda deployed"
    echo "  Function: $DQ_LAMBDA"
else
    echo "⚠ Data Quality Lambda not found"
fi
echo ""

# 8. Check Step Functions
echo "8. VERIFYING STEP FUNCTIONS PIPELINE"
echo "====================================="
SF_ARN=$(aws stepfunctions list-state-machines --query 'stateMachines[?contains(name, `noaa`)].stateMachineArn' --output text 2>/dev/null)
if [ -n "$SF_ARN" ]; then
    echo "✓ Step Functions state machine exists"
    echo "  ARN: $SF_ARN"
else
    echo "⚠ Step Functions not found (non-critical)"
fi
echo ""

# 9. System Health Summary
echo "================================================================"
echo "SYSTEM HEALTH SUMMARY"
echo "================================================================"
echo ""

# Count components
LAMBDA_COUNT=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' --output text | wc -w)
CRAWLER_COUNT=$(aws glue list-crawlers --query 'CrawlerNames' --output text | wc -w)
RULE_COUNT=$(aws events list-rules --query 'Rules[?contains(Name, `noaa`) && State==`ENABLED`].Name' --output text | wc -w)
DB_COUNT=$(aws athena list-databases --catalog-name AwsDataCatalog --query 'DatabaseList[?contains(Name, `noaa`)].Name' --output text | wc -w)

echo "Component Status:"
echo "  Lambda Functions:      $LAMBDA_COUNT deployed"
echo "  Glue Crawlers:         $CRAWLER_COUNT deployed"
echo "  EventBridge Rules:     $RULE_COUNT enabled"
echo "  Athena Databases:      $DB_COUNT created"
echo "  CloudWatch Dashboard:  $([ -n "$DASHBOARD" ] && echo "✓ Created" || echo "✗ Missing")"
echo "  Data Quality Lambda:   $([ "$DQ_LAMBDA" = "noaa-data-quality-dev" ] && echo "✓ Deployed" || echo "✗ Missing")"
echo ""

# Calculate overall health score
TOTAL_CHECKS=8
PASSED_CHECKS=0

[ $LAMBDA_COUNT -ge 7 ] && ((PASSED_CHECKS++))
[ $CRAWLER_COUNT -ge 12 ] && ((PASSED_CHECKS++))
[ $RULE_COUNT -ge 6 ] && ((PASSED_CHECKS++))
[ $DB_COUNT -ge 2 ] && ((PASSED_CHECKS++))
[ -n "$DASHBOARD" ] && ((PASSED_CHECKS++))
[ "$DQ_LAMBDA" = "noaa-data-quality-dev" ] && ((PASSED_CHECKS++))
[ -n "$SF_ARN" ] && ((PASSED_CHECKS++))

# Always count data ingestion as passed if ponds have data
[ $(aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/atmospheric/ --recursive 2>/dev/null | wc -l) -gt 0 ] && ((PASSED_CHECKS++))

HEALTH_SCORE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

echo "Overall Health Score: $HEALTH_SCORE/100"
echo ""

if [ $HEALTH_SCORE -ge 90 ]; then
    echo "Status: ✅ EXCELLENT - System is fully operational"
elif [ $HEALTH_SCORE -ge 75 ]; then
    echo "Status: ✅ GOOD - System is operational"
elif [ $HEALTH_SCORE -ge 50 ]; then
    echo "Status: ⚠️  FAIR - Some components need attention"
else
    echo "Status: ❌ CRITICAL - System requires immediate attention"
fi

echo ""
echo "================================================================"
echo "Verification completed at $(date)"
echo "================================================================"
