#!/bin/bash
# Comprehensive System Audit for Account 899626030376

source config/environment.sh

echo "═══════════════════════════════════════════════════════════════"
echo "NOAA FEDERATED DATA LAKE - COMPREHENSIVE SYSTEM AUDIT"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Date: $(date)"
echo "Account: $AWS_ACCOUNT_ID"
echo "Profile: $AWS_PROFILE"
echo "Region: $AWS_REGION"
echo "Environment: $ENVIRONMENT"
echo ""

# 1. Lambda Functions
echo "═══════════════════════════════════════════════════════════════"
echo "1. LAMBDA FUNCTIONS"
echo "═══════════════════════════════════════════════════════════════"
aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].{Name:FunctionName,Runtime:Runtime,Memory:MemorySize,Timeout:Timeout,Modified:LastModified,State:State}' --output table
echo ""

# 2. EventBridge Rules
echo "═══════════════════════════════════════════════════════════════"
echo "2. EVENTBRIDGE RULES"
echo "═══════════════════════════════════════════════════════════════"
aws events list-rules --query 'Rules[?contains(Name, `noaa`)].{Name:Name,State:State,Schedule:ScheduleExpression}' --output table
echo ""

# 3. S3 Buckets
echo "═══════════════════════════════════════════════════════════════"
echo "3. S3 BUCKETS"
echo "═══════════════════════════════════════════════════════════════"
echo "Data Lake Bucket:"
aws s3 ls s3://${DATA_LAKE_BUCKET}/ 2>&1 | head -10
echo ""
echo "Recent Bronze Data (Atmospheric):"
aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/atmospheric/ --recursive --human-readable | tail -5
echo ""
echo "Bronze Layer Statistics:"
aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/ --recursive --summarize | tail -2
echo ""
echo "Gold Layer Statistics:"
aws s3 ls s3://${DATA_LAKE_BUCKET}/gold/ --recursive --summarize 2>&1 | tail -2
echo ""

# 4. Athena Databases
echo "═══════════════════════════════════════════════════════════════"
echo "4. ATHENA DATABASES & TABLES"
echo "═══════════════════════════════════════════════════════════════"
echo "Databases:"
aws athena list-databases --catalog-name AwsDataCatalog --query 'DatabaseList[?contains(Name, `noaa`)].Name' --output table
echo ""

# 5. IAM Roles
echo "═══════════════════════════════════════════════════════════════"
echo "5. IAM ROLES"
echo "═══════════════════════════════════════════════════════════════"
aws iam list-roles --query 'Roles[?contains(RoleName, `noaa`)].{Name:RoleName,Created:CreateDate}' --output table
echo ""

# 6. CloudWatch Logs
echo "═══════════════════════════════════════════════════════════════"
echo "6. CLOUDWATCH LOG GROUPS"
echo "═══════════════════════════════════════════════════════════════"
aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `noaa`)].{Name:logGroupName,Size:storedBytes,Retention:retentionInDays}' --output table
echo ""

# 7. Recent Lambda Invocations
echo "═══════════════════════════════════════════════════════════════"
echo "7. RECENT LAMBDA INVOCATIONS (Last Hour)"
echo "═══════════════════════════════════════════════════════════════"
echo "Checking atmospheric ingestion..."
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=${LAMBDA_ATMOSPHERIC} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --query 'Datapoints[0].Sum' \
  --output text 2>&1 | head -1
echo ""

# 8. Lambda Errors
echo "═══════════════════════════════════════════════════════════════"
echo "8. LAMBDA ERRORS (Last Hour)"
echo "═══════════════════════════════════════════════════════════════"
echo "Checking atmospheric errors..."
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=${LAMBDA_ATMOSPHERIC} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --query 'Datapoints[0].Sum' \
  --output text 2>&1 | head -1
echo ""

# 9. Data Freshness Check
echo "═══════════════════════════════════════════════════════════════"
echo "9. DATA FRESHNESS CHECK"
echo "═══════════════════════════════════════════════════════════════"
echo "Checking each pond for recent data..."
for pond in atmospheric oceanic buoy climate terrestrial spatial; do
    echo -n "${pond}: "
    latest=$(aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/${pond}/ --recursive 2>/dev/null | tail -1 | awk '{print $1, $2}')
    if [ -n "$latest" ]; then
        echo "$latest"
    else
        echo "No data found"
    fi
done
echo ""

# 10. System Health Score
echo "═══════════════════════════════════════════════════════════════"
echo "10. SYSTEM HEALTH SCORE"
echo "═══════════════════════════════════════════════════════════════"

SCORE=0
MAX_SCORE=10

# Check Lambda functions (2 points)
LAMBDA_COUNT=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa-ingest`)].FunctionName' --output text | wc -w)
if [ "$LAMBDA_COUNT" -ge 6 ]; then
    echo "✓ Lambda Functions: $LAMBDA_COUNT/6+ deployed (+2 points)"
    ((SCORE+=2))
else
    echo "✗ Lambda Functions: Only $LAMBDA_COUNT deployed (0 points)"
fi

# Check EventBridge (1 point)
RULE_COUNT=$(aws events list-rules --query 'Rules[?contains(Name, `noaa`) && State==`ENABLED`].Name' --output text | wc -w)
if [ "$RULE_COUNT" -ge 6 ]; then
    echo "✓ EventBridge Rules: $RULE_COUNT enabled (+1 point)"
    ((SCORE+=1))
else
    echo "✗ EventBridge Rules: Only $RULE_COUNT enabled (0 points)"
fi

# Check S3 Data Lake (2 points)
if aws s3 ls s3://${DATA_LAKE_BUCKET}/ &>/dev/null; then
    echo "✓ Data Lake Bucket: Accessible (+1 point)"
    ((SCORE+=1))
    
    # Check for recent data
    RECENT=$(aws s3 ls s3://${DATA_LAKE_BUCKET}/bronze/atmospheric/ --recursive | grep "$(date +%Y-%m-%d)" | wc -l)
    if [ "$RECENT" -gt 0 ]; then
        echo "✓ Recent Data: $RECENT files today (+1 point)"
        ((SCORE+=1))
    else
        echo "✗ Recent Data: No data ingested today (0 points)"
    fi
else
    echo "✗ Data Lake Bucket: Not accessible (0 points)"
fi

# Check Athena (1 point)
DB_COUNT=$(aws athena list-databases --catalog-name AwsDataCatalog --query 'DatabaseList[?contains(Name, `noaa`)].Name' --output text | wc -w)
if [ "$DB_COUNT" -ge 1 ]; then
    echo "✓ Athena Databases: $DB_COUNT found (+1 point)"
    ((SCORE+=1))
else
    echo "✗ Athena Databases: None found (0 points)"
fi

# Check IAM Roles (1 point)
ROLE_COUNT=$(aws iam list-roles --query 'Roles[?contains(RoleName, `noaa`)].RoleName' --output text | wc -w)
if [ "$ROLE_COUNT" -ge 1 ]; then
    echo "✓ IAM Roles: $ROLE_COUNT configured (+1 point)"
    ((SCORE+=1))
else
    echo "✗ IAM Roles: None found (0 points)"
fi

# Check for errors (2 points)
ERROR_COUNT=$(aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=${LAMBDA_ATMOSPHERIC} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --query 'Datapoints[0].Sum' \
  --output text 2>&1 | grep -v "None" | head -1)

if [ -z "$ERROR_COUNT" ] || [ "$ERROR_COUNT" = "None" ] || [ "$ERROR_COUNT" = "0" ] || [ "$ERROR_COUNT" = "0.0" ]; then
    echo "✓ Error Rate: No errors in last hour (+2 points)"
    ((SCORE+=2))
else
    echo "⚠ Error Rate: $ERROR_COUNT errors in last hour (+1 point)"
    ((SCORE+=1))
fi

# Check AI Query Handler (1 point)
if aws lambda get-function --function-name ${LAMBDA_AI_QUERY} &>/dev/null; then
    echo "✓ AI Query Handler: Deployed (+1 point)"
    ((SCORE+=1))
else
    echo "✗ AI Query Handler: Not deployed (0 points)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "OVERALL HEALTH SCORE: ${SCORE}/${MAX_SCORE}"
echo "═══════════════════════════════════════════════════════════════"

if [ "$SCORE" -ge 9 ]; then
    echo "Status: ✅ EXCELLENT - System is fully operational"
elif [ "$SCORE" -ge 7 ]; then
    echo "Status: ✅ GOOD - System is operational with minor issues"
elif [ "$SCORE" -ge 5 ]; then
    echo "Status: ⚠️ FAIR - System needs attention"
else
    echo "Status: ❌ CRITICAL - System requires immediate attention"
fi

echo ""
echo "Audit completed at $(date)"
echo "═══════════════════════════════════════════════════════════════"
