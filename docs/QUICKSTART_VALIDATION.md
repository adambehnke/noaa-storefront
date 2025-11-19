# NOAA Federated Data Lake - Quick Start Validation Guide

**Purpose:** Get started testing the system in under 5 minutes

---

## Prerequisites

```bash
# Verify you have the required tools
which aws curl jq

# Configure AWS credentials if not already done
aws configure
```

---

## 1. Quick System Health Check (30 seconds)

```bash
# Test the Federated API is responding
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "hello"}' | jq -r '.answer'
```

**Expected:** Should return a response (even if it says it needs more specific data)

---

## 2. Test NOAA Data is Flowing (1 minute)

### Test Oceanic Data (Water Temperature)

```bash
# Direct from NOAA
echo "=== Direct NOAA API ==="
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&date=latest&time_zone=GMT&units=metric&format=json" | jq '.data[0]'

# Via Federated API
echo ""
echo "=== Via Federated API ==="
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in Florida?"}' | jq -r '.answer'
```

### Test Atmospheric Data (Weather)

```bash
echo "=== Current Weather ==="
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current weather in New York City?"}' | jq -r '.answer'
```

---

## 3. Verify Data Lake (2 minutes)

### Check Bronze Layer

```bash
echo "=== Bronze Layer Files (last 10) ==="
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/ --recursive | tail -10
```

### Check Gold Layer

```bash
echo "=== Starting Athena Query ==="
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT station_id, station_name, avg_water_temp, date FROM noaa_gold_dev.oceanic_aggregated ORDER BY date DESC LIMIT 5" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/ \
  --output text --query 'QueryExecutionId')

echo "Query ID: $QUERY_ID"
echo "Waiting 5 seconds for query to complete..."
sleep 5

aws athena get-query-results --query-execution-id $QUERY_ID --output json | jq '.ResultSet.Rows'
```

---

## 4. Run Comprehensive Validation (5 minutes)

```bash
cd noaa_storefront
./scripts/validate_all_endpoints.sh dev
```

This will:
- Test all NOAA API endpoints (Oceanic, Atmospheric, Buoy, Climate)
- Verify Bronze layer data in S3
- Query Gold layer via Athena
- Test Federated API responses
- Check system health (S3, Athena, Lambda)
- Generate a detailed markdown report

**Output:** `validation_report_YYYYMMDD_HHMMSS.md`

---

## 5. Test Multi-Pond Queries (1 minute)

```bash
# Query spanning multiple data ponds
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather in Florida and what is the water temperature in the bay?"
  }' | jq '.'
```

**Look for:** Response should include `data_sources` array showing both atmospheric and oceanic ponds

---

## 6. Verify Data Provenance (30 seconds)

```bash
# Extract just the data sources
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in Florida?"}' | jq '.data_sources'
```

**Expected output:**
```json
[
  {
    "pond": "oceanic",
    "endpoint": "https://api.tidesandcurrents.noaa.gov/...",
    "lake_layer": "gold",
    "table": "oceanic_aggregated"
  }
]
```

---

## Quick Troubleshooting

### Problem: API returns 500 error

```bash
# Check Lambda logs
aws logs tail /aws/lambda/noaa-enhanced-handler-dev --follow
```

### Problem: No data in Bronze layer

```bash
# Manually trigger ingestion
aws lambda invoke \
  --function-name noaa-ingest-oceanic-dev \
  --payload '{"hours_back": 24, "env": "dev"}' \
  output.json

cat output.json | jq '.'
```

### Problem: Athena returns no results

```bash
# Repair table partitions
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE noaa_gold_dev.oceanic_aggregated" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

---

## Common Test Queries

### Single Pond Queries

```bash
# Oceanic - Water Temperature
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in Florida?"}'

# Oceanic - Water Levels
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the water levels in Boston Harbor?"}'

# Atmospheric - Current Weather
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current weather in Chicago?"}'

# Atmospheric - Alerts
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "Are there any weather warnings in California?"}'
```

### Multi-Question Queries

```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Boston? What are the water levels? Any alerts in Massachusetts?"}'
```

---

## What's Working vs Not Yet Implemented

### ✅ Currently Operational

- **Oceanic Pond**
  - ✅ Water Temperature (full medallion: Bronze → Silver → Gold)
  - ✅ Water Levels (full medallion: Bronze → Silver → Gold)
  
- **Atmospheric Pond**
  - ✅ Current Weather (pass-through API)
  - ✅ Weather Alerts (pass-through API)
  - ✅ Forecasts (pass-through API)

### ⚠️ Planned But Not Yet Built

- **Oceanic Pond**
  - ⚠️ Tide Predictions
  - ⚠️ Currents
  - ⚠️ Salinity

- **Buoy Pond**
  - ⚠️ NDBC Buoy observations (API accessible, ingestion not built)

- **Climate Pond**
  - ⚠️ Historical climate data (API token configured, ingestion not built)

- **Terrestrial Pond**
  - ⚠️ Drought Monitor
  - ⚠️ Soil Moisture

---

## Next Steps

1. **Run full validation:** `./scripts/validate_all_endpoints.sh dev`
2. **Review the report:** `cat validation_report_*.md`
3. **Check detailed docs:** `docs/NOAA_ENDPOINT_VALIDATION.md`
4. **See all curl examples:** `docs/CURL_EXAMPLES.md`
5. **Read full summary:** `TESTING_FRAMEWORK_SUMMARY.md`

---

## Success Indicators

You'll know the system is healthy when:

- ✅ Federated API responds within 2-3 seconds
- ✅ Bronze layer has files updated within last 24 hours
- ✅ Athena queries return data for current date
- ✅ API responses include `data_sources` showing NOAA origins
- ✅ No errors in Lambda CloudWatch logs
- ✅ All test queries return formatted responses

---

## Resources

- **Federated API:** https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask
- **Web App:** https://dq8oz5pgpnqc1.cloudfront.net
- **Testing Docs:** `docs/`
- **Validation Script:** `scripts/validate_all_endpoints.sh`

---

**Last Updated:** 2024  
**Time to Complete:** 10-15 minutes total