# 🎯 NOAA Data Lake - Complete Action Plan

**Goal:** Enable plain English queries to a unified data lake with intelligent multi-pond routing and passthrough to NOAA sources

**Status Date:** 2025-11-05

---

## 📊 Current Status

### ✅ What's Working (95%)
- **Infrastructure:** CloudFormation stack deployed
- **Storage:** S3 buckets with Bronze/Silver/Gold layers
- **Data Ingestion:** 527 weather alerts + 6 observations in Bronze layer
- **AI Endpoint:** `/ask` accepts plain English queries
- **Data API:** `/data` for traditional queries
- **Automation:** Pipeline runs every 6 hours
- **AI Models:** Bedrock integration working (intent recognition, routing, synthesis)

### ⚠️ What Needs Completion (5%)
1. **SQL Date Functions** - Blocking AI queries from returning real data
2. **Gold Layer Population** - Need aggregated data for queries
3. **Passthrough Queries** - Direct NOAA API access not implemented
4. **Data Source Discovery** - User shouldn't need to know which pond/source
5. **Multi-Pond Orchestration** - Cross-pond queries need testing
6. **Additional Data Sources** - Only NWS implemented; need Tides, CDO, etc.

---

## 🚀 Phase 1: Fix Core Functionality (1-2 hours)

### Task 1.1: Fix SQL Date Functions ⚡ HIGH PRIORITY
**Problem:** Athena doesn't support MySQL-style `DATE_SUB()` function
**Impact:** AI queries return no data even though data exists

**Solution:**
```bash
# Edit ai_query_orchestrator.py
# Line ~410-415, replace:
#   date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
# With:
#   date >= date_add('day', -30, current_date)

# Or use static date:
#   date >= DATE '2025-10-01'
```

**Steps:**
1. Open `ai_query_orchestrator.py`
2. Find the `generate_sql_for_pond()` function
3. Replace fallback SQL generation:
```python
# OLD:
fallback_sql = f"SELECT * FROM {table} WHERE date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY) LIMIT 100"

# NEW:
fallback_sql = f"SELECT * FROM {table} WHERE date >= date_add('day', -30, current_date) LIMIT 100"
```
4. Also update SQL generation prompt to use Athena-compatible functions
5. Deploy: `./deploy.sh dev us-east-1`

**Test:**
```bash
curl -X POST "https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Show me recent weather alerts"}'
```

**Expected:** Should return data from Gold layer

---

### Task 1.2: Populate Gold Layer ⚡ HIGH PRIORITY
**Problem:** Gold tables exist but have no data
**Impact:** All queries return empty results

**Solution A: Manual ETL (5 minutes)**
```sql
-- Run in Athena console
CREATE TABLE noaa_gold_dev.atmospheric_aggregated AS
SELECT 
  COALESCE(
    CASE 
      WHEN properties.areaDesc LIKE '%CA%' OR properties.areaDesc LIKE '%California%' THEN 'CA'
      WHEN properties.areaDesc LIKE '%TX%' OR properties.areaDesc LIKE '%Texas%' THEN 'TX'
      WHEN properties.areaDesc LIKE '%FL%' OR properties.areaDesc LIKE '%Florida%' THEN 'FL'
      WHEN properties.areaDesc LIKE '%NY%' OR properties.areaDesc LIKE '%New York%' THEN 'NY'
      ELSE 'Other'
    END, 'Unknown'
  ) as region,
  properties.event as event_type,
  properties.severity as severity,
  properties.certainty as certainty,
  COUNT(*) as alert_count,
  CAST(SUBSTR(properties.onset, 1, 10) AS DATE) as date
FROM noaa_bronze_dev.atmospheric_raw
WHERE properties.onset IS NOT NULL
GROUP BY 
  CASE 
    WHEN properties.areaDesc LIKE '%CA%' OR properties.areaDesc LIKE '%California%' THEN 'CA'
    WHEN properties.areaDesc LIKE '%TX%' OR properties.areaDesc LIKE '%Texas%' THEN 'TX'
    WHEN properties.areaDesc LIKE '%FL%' OR properties.areaDesc LIKE '%Florida%' THEN 'FL'
    WHEN properties.areaDesc LIKE '%NY%' OR properties.areaDesc LIKE '%New York%' THEN 'NY'
    ELSE 'Other'
  END,
  properties.event, 
  properties.severity,
  properties.certainty,
  CAST(SUBSTR(properties.onset, 1, 10) AS DATE);
```

**Solution B: Run Step Functions Pipeline (10 minutes)**
```bash
# Get state machine ARN
STATE_MACHINE=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn "$STATE_MACHINE" \
  --input '{"trigger":"manual","timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'

# Monitor (takes ~5-10 min)
aws stepfunctions list-executions \
  --state-machine-arn "$STATE_MACHINE" \
  --max-results 1
```

**Verify:**
```sql
-- Should return rows
SELECT COUNT(*) FROM noaa_gold_dev.atmospheric_aggregated;

-- Should show regions and counts
SELECT region, COUNT(*) as cnt 
FROM noaa_gold_dev.atmospheric_aggregated 
GROUP BY region;
```

---

## 🔄 Phase 2: Implement Passthrough Queries (2-3 hours)

### Task 2.1: Add NOAA Direct Query Handler

**Concept:** Allow users to query NOAA APIs directly when Gold layer doesn't have data

**Create:** `noaa_passthrough_handler.py`

```python
import json
import os
import boto3
import requests
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """
    Passthrough handler for direct NOAA API queries
    Routes to appropriate NOAA API based on pond/service
    """
    
    params = event.get('queryStringParameters', {})
    service = params.get('service', 'nws')
    
    # Route to appropriate handler
    if service in ['nws', 'atmospheric']:
        return query_nws_api(params)
    elif service in ['tides', 'oceanic']:
        return query_tides_api(params)
    elif service in ['cdo', 'climate']:
        return query_cdo_api(params)
    else:
        return respond(400, {'error': f'Unknown service: {service}'})

def query_nws_api(params):
    """Query NWS API directly"""
    endpoint = params.get('endpoint', 'alerts/active')
    
    response = requests.get(
        f"https://api.weather.gov/{endpoint}",
        headers={
            'User-Agent': 'NOAA-Federated-Lake/1.0',
            'Accept': 'application/geo+json'
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        return respond(200, {
            'source': 'noaa_nws_api',
            'service': 'atmospheric',
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })
    else:
        return respond(response.status_code, {
            'error': 'NOAA API error',
            'details': response.text
        })

def query_tides_api(params):
    """Query Tides & Currents API directly"""
    station = params.get('station', '9414290')  # Default: San Francisco
    product = params.get('product', 'water_level')
    
    begin_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y%m%d')
    end_date = datetime.utcnow().strftime('%Y%m%d')
    
    response = requests.get(
        'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter',
        params={
            'product': product,
            'station': station,
            'begin_date': begin_date,
            'end_date': end_date,
            'time_zone': 'GMT',
            'units': 'metric',
            'format': 'json',
            'application': 'NOAA_Lake'
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        return respond(200, {
            'source': 'noaa_tides_api',
            'service': 'oceanic',
            'station': station,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })
    else:
        return respond(response.status_code, {
            'error': 'Tides API error',
            'details': response.text
        })

def query_cdo_api(params):
    """Query Climate Data Online API"""
    token = os.environ.get('NOAA_CDO_TOKEN')
    if not token:
        return respond(400, {
            'error': 'CDO API token not configured',
            'message': 'Set NOAA_CDO_TOKEN environment variable'
        })
    
    dataset = params.get('dataset', 'GHCND')
    location = params.get('location', 'FIPS:06')  # California
    
    response = requests.get(
        f'https://www.ncdc.noaa.gov/cdo-web/api/v2/data',
        headers={'token': token},
        params={
            'datasetid': dataset,
            'locationid': location,
            'startdate': (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'enddate': datetime.utcnow().strftime('%Y-%m-%d'),
            'limit': 100
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        return respond(200, {
            'source': 'noaa_cdo_api',
            'service': 'climate',
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        })
    else:
        return respond(response.status_code, {
            'error': 'CDO API error',
            'details': response.text
        })

def respond(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body, default=str)
    }
```

**Deploy:**
```bash
# Package
cd noaa_storefront
zip -r noaa_passthrough.zip noaa_passthrough_handler.py

# Upload
aws lambda create-function \
  --function-name noaa-passthrough-dev \
  --runtime python3.11 \
  --role arn:aws:iam::349338457682:role/noaa-lambda-execution-dev \
  --handler noaa_passthrough_handler.lambda_handler \
  --zip-file fileb://noaa_passthrough.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{NOAA_CDO_TOKEN=YOUR_TOKEN}"

# Add API Gateway endpoint
aws apigatewayv2 create-route \
  --api-id z0rld53i7a \
  --route-key "GET /passthrough" \
  --target "integrations/$(aws apigatewayv2 create-integration \
    --api-id z0rld53i7a \
    --integration-type AWS_PROXY \
    --integration-uri arn:aws:lambda:us-east-1:349338457682:function:noaa-passthrough-dev \
    --payload-format-version 2.0 \
    --query 'IntegrationId' --output text)"
```

**Test:**
```bash
# Query NWS directly
curl "https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/passthrough?service=nws&endpoint=alerts/active"

# Query Tides directly
curl "https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/passthrough?service=tides&station=9414290"
```

---

### Task 2.2: Integrate Passthrough with AI Orchestrator

**Goal:** When Gold layer has no data, automatically fallback to passthrough

**Edit:** `ai_query_orchestrator.py`

Add to `execute_athena_query()` function:

```python
def execute_athena_query(sql, pond_name, max_wait=30):
    """Execute Athena query with passthrough fallback"""
    
    try:
        # Try Athena first
        query_id = start_query(sql)
        results = wait_for_results(query_id, max_wait)
        
        if results and len(results) > 0:
            return {
                'source': 'gold_layer',
                'pond': pond_name,
                'data': results,
                'record_count': len(results)
            }
        else:
            # No data in Gold layer, try passthrough
            logger.info(f"No data in Gold layer for {pond_name}, trying passthrough")
            return try_passthrough(pond_name)
            
    except Exception as e:
        logger.error(f"Athena query failed: {e}")
        # Fallback to passthrough
        return try_passthrough(pond_name)

def try_passthrough(pond_name):
    """Query NOAA APIs directly when Gold layer is empty"""
    
    # Invoke passthrough Lambda
    lambda_client = boto3.client('lambda')
    
    payload = {
        'queryStringParameters': {
            'service': pond_name
        }
    }
    
    response = lambda_client.invoke(
        FunctionName='noaa-passthrough-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    result = json.loads(response['Payload'].read())
    body = json.loads(result.get('body', '{}'))
    
    return {
        'source': 'noaa_api_passthrough',
        'pond': pond_name,
        'data': body.get('data', []),
        'record_count': len(body.get('data', [])) if isinstance(body.get('data'), list) else 1
    }
```

---

## 🎨 Phase 3: Enhance Multi-Pond Intelligence (3-4 hours)

### Task 3.1: Improve AI Pond Routing

**Current Issue:** User must know which pond has their data

**Solution:** Make AI smarter about data discovery

**Edit:** `ai_query_config.yaml` - Add more training examples:

```yaml
ponds:
  - name: atmospheric
    description: Weather alerts, forecasts, observations, storms, temperature, precipitation
    keywords: [weather, alert, storm, temperature, rain, snow, wind, forecast, warning, advisory]
    sample_queries:
      - "What's the weather like?"
      - "Are there any alerts?"
      - "Show me storm activity"
      - "What's the temperature?"
      - "Is it going to rain?"
    
  - name: oceanic
    description: Tides, currents, water levels, ocean temperature, marine conditions
    keywords: [tide, ocean, water, marine, coastal, current, sea, beach]
    sample_queries:
      - "What are the tide predictions?"
      - "When is high tide?"
      - "Show me ocean temperatures"
      - "Is it safe to go to the beach?"
    
  - name: climate
    description: Historical climate data, temperature normals, precipitation records
    keywords: [climate, historical, trend, record, average, normal, past, history]
    sample_queries:
      - "What are historical temperatures?"
      - "Show me climate trends"
      - "Is this hotter than normal?"
```

### Task 3.2: Implement Smart Data Discovery

**Goal:** User asks vague question, system searches ALL ponds

**Add to:** `ai_query_orchestrator.py`

```python
def search_all_ponds(query_intent):
    """
    When user's query is vague, search across all ponds
    and return relevant data from any source
    """
    
    all_ponds = ['atmospheric', 'oceanic', 'climate', 'terrestrial', 'spatial']
    results = {}
    
    for pond in all_ponds:
        try:
            # Generate generic query for each pond
            sql = f"SELECT * FROM {get_gold_table(pond)} ORDER BY date DESC LIMIT 10"
            
            data = execute_athena_query(sql, pond, max_wait=10)
            
            if data.get('record_count', 0) > 0:
                results[pond] = data
                
        except Exception as e:
            logger.debug(f"No data in {pond}: {e}")
            continue
    
    return results
```

---

## 📦 Phase 4: Populate All Data Ponds (4-6 hours)

### Task 4.1: Enable Tides & Currents (Oceanic Pond)

**Script:** `scripts/bronze_ingest_tides.py` (already exists)

**Deploy:**
```bash
# Upload script
aws s3 cp scripts/bronze_ingest_tides.py \
  s3://noaa-deployment-349338457682-dev/glue-scripts/

# Create Glue job
aws glue create-job \
  --name noaa-ingest-tides-dev \
  --role noaa-glue-role-dev \
  --command "Name=pythonshell,ScriptLocation=s3://noaa-deployment-349338457682-dev/glue-scripts/bronze_ingest_tides.py,PythonVersion=3.9" \
  --default-arguments '{"--LAKE_BUCKET":"noaa-federated-lake-349338457682-dev","--ENV":"dev"}' \
  --max-capacity 0.0625

# Run it
aws glue start-job-run --job-name noaa-ingest-tides-dev
```

**Add to Step Functions:** Update `noaa_medallion_pipeline.asl.json` to include tides ingestion

### Task 4.2: Enable Climate Data (CDO)

**Requires:** NOAA CDO API token from https://www.ncdc.noaa.gov/cdo-web/token

```bash
# Store token in Secrets Manager
aws secretsmanager create-secret \
  --name noaa-cdo-token-dev \
  --secret-string "YOUR_TOKEN_HERE"

# Update Lambda environment
aws lambda update-function-configuration \
  --function-name noaa-bronze-ingest-dev \
  --environment Variables="{NOAA_CDO_TOKEN_SECRET=noaa-cdo-token-dev}"
```

### Task 4.3: Add More NWS Endpoints

**Currently implemented:** 
- Alerts
- Observations

**To add (quick wins):**
- Forecasts: `/points/{lat},{lon}/forecast`
- Radar stations: `/radar/stations`
- Active zones: `/zones?type=forecast`

---

## 🧪 Phase 5: End-to-End Testing (1-2 hours)

### Test Suite

```bash
#!/bin/bash
# save as test_e2e.sh

API="https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev"

echo "=== Test 1: Health Check ==="
curl "$API/data?ping=true"

echo -e "\n\n=== Test 2: Plain English - Vague Query ==="
curl -X POST "$API/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"What data do you have?"}'

echo -e "\n\n=== Test 3: Plain English - Specific Region ==="
curl -X POST "$API/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Show me weather in California"}'

echo -e "\n\n=== Test 4: Plain English - Cross-Pond ==="
curl -X POST "$API/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"How do ocean conditions affect weather?"}'

echo -e "\n\n=== Test 5: Direct Data API ==="
curl "$API/data?service=atmospheric&region=CA&limit=10"

echo -e "\n\n=== Test 6: Passthrough to NOAA ==="
curl "$API/passthrough?service=nws&endpoint=alerts/active"

echo -e "\n\n=== Test 7: Data Discovery ==="
curl -X POST "$API/ask" \
  -H "Content-Type: application/json" \
  -d '{"query":"Tell me about environmental conditions"}'
```

Run:
```bash
chmod +x test_e2e.sh
./test_e2e.sh | jq '.'
```

---

## 📈 Phase 6: Production Readiness (Ongoing)

### Monitoring

```bash
# Set up CloudWatch alarms
aws cloudwatch put-metric-alarm \
  --alarm-name noaa-api-errors-dev \
  --alarm-description "Alert on API errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1

# Dashboard
aws cloudwatch put-dashboard \
  --dashboard-name noaa-lake-dev \
  --dashboard-body file://cloudwatch-dashboard.json
```

### Cost Optimization

```yaml
# Add to CloudFormation
BronzeBucket:
  Properties:
    LifecycleConfiguration:
      Rules:
        - Id: TransitionToIA
          Status: Enabled
          Transitions:
            - TransitionInDays: 30
              StorageClass: INTELLIGENT_TIERING
        - Id: ExpireOldData
          Status: Enabled
          ExpirationInDays: 90
```

### Documentation

Create user guide:
- How to ask questions in plain English
- What data sources are available
- How to interpret results
- Example queries for common use cases

---

## 🎯 Success Metrics

### Week 1 Goals
- ✅ Gold layer populated with real data
- ✅ AI queries returning results
- ✅ Passthrough working for all 3 services (NWS, Tides, CDO)
- ✅ 90% query success rate

### Week 2 Goals
- ✅ All 6 data ponds receiving data
- ✅ Cross-pond queries working
- ✅ Data discovery without user knowing source
- ✅ < 2 second average response time

### Week 4 Goals (Production)
- ✅ 99.9% uptime
- ✅ < 5 second p95 latency
- ✅ 10+ data sources ingesting
- ✅ User documentation complete

---

## 🔧 Quick Commands Reference

```bash
# Check what's running
aws cloudformation describe-stacks --stack-name noaa-federated-lake-dev

# View recent logs
aws logs tail /aws/lambda/noaa-ai-orchestrator-dev --follow

# Query data directly
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.atmospheric_aggregated LIMIT 10" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-349338457682-dev/

# Check S3 data
aws s3 ls s3://noaa-federated-lake-349338457682-dev/gold/ --recursive --human-readable

# Restart pipeline
STATE_MACHINE=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)
aws stepfunctions start-execution --state-machine-arn "$STATE_MACHINE"
```

---

## 📞 Support & Troubleshooting

### Issue: "No data returned"
**Check:**
1. Is Gold layer populated? `SELECT COUNT(*) FROM noaa_gold_dev.atmospheric_aggregated`
2. Is date filter too restrictive?
3. Are Glue jobs succeeding? Check CloudWatch logs

### Issue: "SQL syntax error"
**Fix:** Update to Athena-compatible functions
- ❌ `DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)`
- ✅ `date_add('day', -30, current_date)`

### Issue: "Passthrough not working"
**Check:**
1. Is Lambda deployed? `aws lambda get-function --function-name noaa-passthrough-dev`
2. NOAA APIs accessible? `python3 test_noaa_apis.py`
3. Check Lambda logs for errors

---

## 🎉 The Vision

**User Experience:**
```bash
# User doesn't know what data exists, just asks naturally
curl -X POST "$API/ask" -H "Content-Type: application/json" \
  -d '{"query":"Is it safe to go sailing today in San Francisco Bay?"}'

# Response combines:
# - Weather alerts (atmospheric pond)
# - Wind data (atmospheric pond)
# - Tide predictions (oceanic pond)
# - Historical conditions (climate pond)
# + AI synthesis into actionable advice
```

**This is 100% achievable with the current architecture!**

---

**Last Updated:** 2025-11-05
**Next Review:** After Phase 1 completion
**Owner:** Adam Behnke