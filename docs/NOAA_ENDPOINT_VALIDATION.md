# NOAA Endpoint Validation & Testing Document

**Version:** 1.0  
**Date:** 2024  
**Purpose:** Comprehensive validation of NOAA data ingestion through Medallion Architecture

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Methodology](#testing-methodology)
3. [NOAA Endpoints by Data Pond](#noaa-endpoints-by-data-pond)
4. [Validation Workflow](#validation-workflow)
5. [Test Queries](#test-queries)
6. [Troubleshooting](#troubleshooting)

---

## Overview

This document provides a comprehensive testing framework for validating data flow from NOAA APIs through our medallion architecture (Bronze → Silver → Gold) and into the federated chatbot API.

### Architecture Layers

1. **NOAA Source APIs** - Official NOAA web services
2. **Bronze Layer** - Raw JSON data stored in S3 (`s3://noaa-federated-lake-*/bronze/`)
3. **Silver Layer** - Cleaned, validated data in S3 (`s3://noaa-federated-lake-*/silver/`)
4. **Gold Layer** - Aggregated, queryable data via Athena (`noaa_gold_dev` database)
5. **Federated API** - Lambda-based chatbot interface

---

## Testing Methodology

### Validation Steps for Each Endpoint

1. **Direct NOAA API Test** - Verify endpoint returns valid data
2. **Bronze Layer Verification** - Confirm raw data landed in S3
3. **Silver Layer Verification** - Validate data cleaning/transformation
4. **Gold Layer Query** - Test Athena aggregations
5. **Federated API Test** - Verify chatbot returns processed data
6. **Data Quality Check** - Validate accuracy and completeness

---

## NOAA Endpoints by Data Pond

### 1. OCEANIC POND ✅ IMPLEMENTED

**Data Source:** NOAA CO-OPS (Center for Operational Oceanographic Products and Services)  
**Base URL:** `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`  
**Auth:** None required  
**Refresh Rate:** 6 minutes

#### Endpoint 1.1: Water Temperature ✅ ACTIVE

**NOAA Direct Query:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&begin_date=20240101%2000:00&end_date=20240101%2023:59&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

**Expected Response:**
```json
{
  "metadata": {
    "id": "9414290",
    "name": "San Francisco",
    "lat": "37.8063",
    "lon": "-122.4659"
  },
  "data": [
    {"t": "2024-01-01 00:00", "v": "12.5", "f": "0,0,0,0"},
    {"t": "2024-01-01 00:06", "v": "12.4", "f": "0,0,0,0"}
  ]
}
```

**Bronze Layer Verification:**
```bash
# Check S3 for raw data
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/ --recursive

# Download sample file
aws s3 cp s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/date=2024-01-01/station_9414290_20240101_120000.json ./sample_bronze.json

# View content
cat sample_bronze.json | jq '.'
```

**Gold Layer Query:**
```bash
# Query via AWS CLI
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.oceanic_aggregated WHERE station_id = '9414290' ORDER BY date DESC LIMIT 5" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

**Federated API Test:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the water temperature in San Francisco?"
  }'
```

**Expected Chatbot Response:**
```json
{
  "answer": "Based on NOAA data from San Francisco Bay (Station 9414290), the current water temperature is approximately 12.5°C...",
  "data_sources": [
    {
      "pond": "oceanic",
      "endpoint": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
      "station": "9414290",
      "lake_layer": "gold",
      "table": "oceanic_aggregated"
    }
  ],
  "data": {
    "station_id": "9414290",
    "station_name": "San Francisco",
    "avg_water_temp": 12.5,
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

---

#### Endpoint 1.2: Water Levels ✅ ACTIVE

**NOAA Direct Query:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&station=9414290&begin_date=20240101%2000:00&end_date=20240101%2023:59&datum=MLLW&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

**Expected Response:**
```json
{
  "metadata": {
    "id": "9414290",
    "name": "San Francisco",
    "lat": "37.8063",
    "lon": "-122.4659"
  },
  "data": [
    {"t": "2024-01-01 00:00", "v": "1.234", "s": "0.012", "f": "0,0,0,0", "q": "v"},
    {"t": "2024-01-01 00:06", "v": "1.256", "s": "0.011", "f": "0,0,0,0", "q": "v"}
  ]
}
```

**Bronze Layer Verification:**
```bash
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_level/ --recursive
```

**Gold Layer Query:**
```sql
SELECT 
  station_id,
  station_name,
  avg_water_level,
  min_water_level,
  max_water_level,
  date
FROM noaa_gold_dev.oceanic_aggregated 
WHERE station_id = '9414290'
ORDER BY date DESC 
LIMIT 10;
```

**Federated API Test:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the water levels in San Francisco?"
  }'
```

---

#### Endpoint 1.3: Tide Predictions ⚠️ DEFINED (Not Yet Ingested)

**NOAA Direct Query:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=predictions&station=9414290&begin_date=20240101&end_date=20240102&datum=MLLW&time_zone=GMT&units=metric&format=json&interval=hilo&application=NOAA_Federated_DataLake"
```

**Implementation Status:** Endpoint defined in orchestrator but not yet in ingestion pipeline

---

#### Endpoint 1.4: Currents ⚠️ DEFINED (Not Yet Ingested)

**NOAA Direct Query:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=currents&station=PUG1515&begin_date=20240101%2000:00&end_date=20240101%2023:59&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

**Note:** Current stations are different from water level stations. Example: PUG1515 (Puget Sound)

**Implementation Status:** Endpoint defined in orchestrator but not yet in ingestion pipeline

---

#### Endpoint 1.5: Salinity ⚠️ DEFINED (Not Yet Ingested)

**NOAA Direct Query:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=salinity&station=8454000&begin_date=20240101%2000:00&end_date=20240101%2023:59&time_zone=GMT&format=json&application=NOAA_Federated_DataLake"
```

**Implementation Status:** Endpoint defined in orchestrator but not yet in ingestion pipeline

---

### 2. ATMOSPHERIC POND ✅ IMPLEMENTED

**Data Source:** NOAA National Weather Service (NWS) API  
**Base URL:** `https://api.weather.gov`  
**Auth:** None required (User-Agent header recommended)  
**Refresh Rate:** Varies by product

#### Endpoint 2.1: Active Weather Alerts ✅ ACTIVE

**NOAA Direct Query:**
```bash
curl -X GET "https://api.weather.gov/alerts/active" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**State-Specific Query:**
```bash
curl -X GET "https://api.weather.gov/alerts/active?area=CA" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Expected Response:**
```json
{
  "@context": ["https://geojson.org/geojson-ld/geojson-context.jsonld"],
  "type": "FeatureCollection",
  "features": [
    {
      "id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.abc123",
      "type": "Feature",
      "properties": {
        "id": "urn:oid:2.49.0.1.840.0.abc123",
        "areaDesc": "San Francisco Bay Area",
        "severity": "Moderate",
        "certainty": "Likely",
        "urgency": "Expected",
        "event": "Wind Advisory",
        "headline": "Wind Advisory issued January 1 at 10:00AM PST",
        "description": "Northwest winds 20 to 30 mph with gusts up to 45 mph expected...",
        "effective": "2024-01-01T10:00:00-08:00",
        "expires": "2024-01-01T22:00:00-08:00"
      }
    }
  ]
}
```

**Bronze Layer Verification:**
```bash
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/alerts/ --recursive
```

**Gold Layer Query:**
```sql
SELECT 
  region,
  event_type,
  severity,
  alert_count,
  date
FROM noaa_gold_dev.atmospheric_aggregated 
ORDER BY date DESC 
LIMIT 20;
```

**Federated API Test:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Are there any severe weather warnings in California?"
  }'
```

---

#### Endpoint 2.2: Current Weather Conditions ✅ ACTIVE

**NOAA Direct Query:**
```bash
# First, get grid coordinates for a location
curl -X GET "https://api.weather.gov/points/40.7128,-74.0060" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Then get current observations (example for NYC)
curl -X GET "https://api.weather.gov/gridpoints/OKX/33,37" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Federated API Test:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the current weather in New York City?"
  }'
```

---

#### Endpoint 2.3: Weather Forecast ✅ ACTIVE

**NOAA Direct Query:**
```bash
curl -X GET "https://api.weather.gov/gridpoints/OKX/33,37/forecast" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Federated API Test:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather forecast for Chicago?"
  }'
```

---

#### Endpoint 2.4: Station Observations ✅ ACTIVE

**NOAA Direct Query:**
```bash
# List stations
curl -X GET "https://api.weather.gov/stations" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Get specific station observation
curl -X GET "https://api.weather.gov/stations/KJFK/observations/latest" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

---

### 3. BUOY POND ⚠️ DEFINED (Not Yet Implemented)

**Data Source:** NOAA National Data Buoy Center (NDBC)  
**Base URL:** `https://www.ndbc.noaa.gov`  
**Auth:** None required  
**Refresh Rate:** Hourly

#### Endpoint 3.1: Buoy Real-Time Data ⚠️ PLANNED

**NOAA Direct Query:**
```bash
# Latest observations from all buoys (tab-delimited text file)
curl -X GET "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"

# Specific buoy (e.g., Station 46042 - Monterey Bay)
curl -X GET "https://www.ndbc.noaa.gov/data/realtime2/46042.txt"
```

**Expected Response Format (text):**
```
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2024 01 01 12 00  230  8.5 10.2  2.50  12.5  10.2 225 1013.2  15.2  13.5  12.1   MM +0.5    MM
```

**Implementation Status:** Schema defined, ingestion pipeline not yet built

**Planned Gold Layer Query:**
```sql
SELECT 
  station_id,
  location,
  avg_wave_height_m,
  max_wave_height_m,
  avg_wind_speed_mps,
  avg_water_temp_c,
  date
FROM noaa_gold_dev.buoy_aggregated 
ORDER BY date DESC 
LIMIT 10;
```

---

### 4. CLIMATE POND ⚠️ DEFINED (Not Yet Implemented)

**Data Source:** NOAA Climate Data Online (CDO) API  
**Base URL:** `https://www.ncdc.noaa.gov/cdo-web/api/v2`  
**Auth:** ✅ Token Required (stored in AWS Secrets Manager)  
**Refresh Rate:** Daily

#### Endpoint 4.1: Daily Climate Data ⚠️ PLANNED

**NOAA Direct Query:**
```bash
# Requires API token from: https://www.ncdc.noaa.gov/cdo-web/token
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&stationid=GHCND:USW00094728&startdate=2024-01-01&enddate=2024-01-31&limit=1000" \
  -H "token: YOUR_NOAA_CDO_TOKEN"
```

**Expected Response:**
```json
{
  "metadata": {
    "resultset": {
      "offset": 1,
      "count": 31,
      "limit": 1000
    }
  },
  "results": [
    {
      "date": "2024-01-01T00:00:00",
      "datatype": "TMAX",
      "station": "GHCND:USW00094728",
      "attributes": ",,W,2400",
      "value": 56
    },
    {
      "date": "2024-01-01T00:00:00",
      "datatype": "TMIN",
      "station": "GHCND:USW00094728",
      "attributes": ",,W,2400",
      "value": 44
    }
  ]
}
```

**Implementation Status:** API token configured, ingestion pipeline not yet built

**Planned Gold Layer Query:**
```sql
SELECT 
  station_id,
  location,
  data_type,
  avg_value,
  max_value,
  min_value,
  date
FROM noaa_gold_dev.climate_aggregated 
WHERE data_type = 'TMAX'
ORDER BY date DESC 
LIMIT 10;
```

---

### 5. SPATIAL POND ⚠️ PARTIALLY IMPLEMENTED

**Data Source:** NOAA NWS Stations & Zones  
**Base URL:** `https://api.weather.gov`  
**Auth:** None required  
**Refresh Rate:** Weekly

#### Endpoint 5.1: NWS Stations ✅ ACTIVE (via NWS API)

**NOAA Direct Query:**
```bash
curl -X GET "https://api.weather.gov/stations" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Specific state
curl -X GET "https://api.weather.gov/stations?state=CA" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Implementation Status:** Available via NWS API calls, dedicated spatial pond not yet built

---

#### Endpoint 5.2: Forecast Zones ⚠️ DEFINED

**NOAA Direct Query:**
```bash
curl -X GET "https://api.weather.gov/zones/forecast" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Implementation Status:** Defined in orchestrator, dedicated ingestion not yet built

---

### 6. TERRESTRIAL POND ⚠️ DEFINED (Not Yet Implemented)

**Data Source:** Multiple (CPC, Drought Monitor)  
**Auth:** Varies  
**Refresh Rate:** Daily to Weekly

#### Endpoint 6.1: Drought Monitor ⚠️ PLANNED

**NOAA Direct Query:**
```bash
curl -X GET "https://droughtmonitor.unl.edu/data/json/usdm_current.json"
```

**Note:** This is a partner dataset, not directly NOAA but included in NOAA ecosystem

**Implementation Status:** Defined but not implemented

---

#### Endpoint 6.2: Soil Moisture ⚠️ PLANNED

**NOAA Direct Query:**
```bash
# CPC Soil Moisture (web scraping required - no direct JSON API)
curl -X GET "https://www.cpc.ncep.noaa.gov/soilmst/leaky_bucket.shtml"
```

**Implementation Status:** Defined but requires web scraping implementation

---

## Validation Workflow

### Complete End-to-End Test

This test validates data flows through all layers for a single query:

```bash
#!/bin/bash
# complete_validation_test.sh

ENDPOINT="https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask"
QUESTION="What is the water temperature in San Francisco and are there any weather alerts in California?"

echo "========================================="
echo "NOAA Federated Data Lake - End-to-End Test"
echo "========================================="
echo ""

# Step 1: Query NOAA directly
echo "Step 1: Direct NOAA API Queries"
echo "-----------------------------------"
echo ""
echo "1.1 Water Temperature from CO-OPS:"
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&date=latest&time_zone=GMT&units=metric&format=json" | jq '.data[0]'
echo ""

echo "1.2 Weather Alerts from NWS:"
curl -s "https://api.weather.gov/alerts/active?area=CA" -H "User-Agent: Test/1.0" | jq '.features | length'
echo " active alerts found"
echo ""

# Step 2: Check Bronze Layer
echo "Step 2: Bronze Layer Verification"
echo "-----------------------------------"
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/ --recursive | tail -5
echo ""

# Step 3: Check Gold Layer
echo "Step 3: Gold Layer Query (Athena)"
echo "-----------------------------------"
echo "Querying oceanic_aggregated table..."
# Note: This requires async query handling
echo ""

# Step 4: Federated API Test
echo "Step 4: Federated API Query"
echo "-----------------------------------"
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"$QUESTION\"}" | jq '.'
echo ""

echo "========================================="
echo "Test Complete"
echo "========================================="
```

---

## Test Queries

### Multi-Pond Federated Queries

Test the system's ability to query multiple data ponds simultaneously:

#### Query 1: Cross-Pond Weather + Ocean
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather in San Francisco and what is the water temperature in the bay?"
  }'
```

**Expected Data Sources:**
- Atmospheric pond (NWS weather)
- Oceanic pond (CO-OPS temperature)

---

#### Query 2: Regional Alert Summary
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Are there any weather warnings or alerts in the Pacific Northwest?"
  }'
```

**Expected Data Sources:**
- Atmospheric pond (NWS alerts)

---

#### Query 3: Coastal Conditions
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the water levels and temperatures along the California coast?"
  }'
```

**Expected Data Sources:**
- Oceanic pond (multiple stations)

---

### Athena Direct Queries

Test Gold layer directly via Athena:

#### Query Oceanic Aggregations
```sql
-- Latest water conditions by station
SELECT 
  station_id,
  station_name,
  state,
  region,
  avg_water_temp,
  avg_water_level,
  date,
  timestamp
FROM noaa_gold_dev.oceanic_aggregated 
WHERE date = current_date
ORDER BY region, state, station_name;
```

#### Query Atmospheric Alerts
```sql
-- Recent severe weather by region
SELECT 
  region,
  event_type,
  severity,
  alert_count,
  date
FROM noaa_gold_dev.atmospheric_aggregated 
WHERE date >= current_date - interval '7' day
  AND severity IN ('Severe', 'Extreme')
ORDER BY date DESC, alert_count DESC;
```

#### Federated Query Log
```sql
-- Track which ponds are being queried
SELECT 
  query_id,
  user_query,
  intent,
  ponds_queried,
  query_timestamp,
  response_time_ms
FROM noaa_gold_dev.federated_query_log 
ORDER BY query_timestamp DESC 
LIMIT 20;
```

---

## Troubleshooting

### Common Issues

#### Issue 1: No Data in Bronze Layer
**Symptoms:** S3 bronze folder empty or outdated
**Diagnosis:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/noaa-ingest-oceanic-dev --follow

# Check EventBridge schedule
aws events list-rules --name-prefix noaa-ingest
```

**Resolution:**
- Verify Lambda has S3 write permissions
- Check EventBridge trigger is enabled
- Manually invoke Lambda: `aws lambda invoke --function-name noaa-ingest-oceanic-dev output.json`

---

#### Issue 2: Athena Query Fails
**Symptoms:** Gold layer queries return no results
**Diagnosis:**
```bash
# Verify tables exist
aws athena start-query-execution \
  --query-string "SHOW TABLES IN noaa_gold_dev" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/

# Check partitions
aws athena start-query-execution \
  --query-string "SHOW PARTITIONS noaa_gold_dev.oceanic_aggregated" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

**Resolution:**
- Run `MSCK REPAIR TABLE noaa_gold_dev.oceanic_aggregated` to discover partitions
- Verify S3 data exists in expected partition structure: `date=YYYY-MM-DD/`

---

#### Issue 3: Chatbot Returns No Data
**Symptoms:** API returns error or empty response
**Diagnosis:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/noaa-enhanced-handler-dev --follow

# Test Lambda directly
aws lambda invoke \
  --function-name noaa-enhanced-handler-dev \
  --payload '{"body": "{\"question\": \"test\"}"}' \
  response.json

cat response.json | jq '.'
```

**Resolution:**
- Verify Lambda has Athena query permissions
- Check environment variables: `GOLD_DB`, `ATHENA_OUTPUT`
- Ensure Bedrock model access if using AI features

---

#### Issue 4: NOAA API Rate Limiting
**Symptoms:** 429 status codes from NOAA
**Diagnosis:**
```bash
# Check ingestion frequency
aws events describe-rule --name noaa-ingest-schedule-dev
```

**Resolution:**
- Reduce ingestion frequency
- Add exponential backoff to Lambda functions
- Implement caching layer

---

## Summary

### Currently Operational

| Pond | Endpoint | Status | Bronze | Silver | Gold | Federated API |
|------|----------|--------|--------|--------|------|---------------|
| **Oceanic** | Water Temperature | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| **Oceanic** | Water Levels | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| **Atmospheric** | Weather Alerts | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| **Atmospheric** | Current Weather | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Atmospheric** | Forecasts | ✅ | ❌ | ❌ | ❌ | ✅ |

✅ = Fully Implemented  
⚠️ = Partially Implemented / Pass-through  
❌ = Not Yet Implemented

### Planned Implementation

| Pond | Endpoint | Priority | Est. Effort |
|------|----------|----------|-------------|
| **Oceanic** | Tide Predictions | High | 2-3 days |
| **Oceanic** | Currents | High | 2-3 days |
| **Oceanic** | Salinity | Medium | 2-3 days |
| **Buoy** | Real-time Observations | High | 3-5 days |
| **Climate** | CDO Historical Data | Medium | 5-7 days |
| **Spatial** | Stations/Zones | Low | 2-3 days |
| **Terrestrial** | Drought Monitor | Low | 3-5 days |

---

## Next Steps

1. **Complete Bronze/Silver/Gold for Atmospheric Pond**
   - Currently uses pass-through to NWS API
   - Need full medallion implementation for consistency

2. **Implement Buoy Pond Ingestion**
   - High value for marine use cases
   - Text parsing required (not JSON)

3. **Add Climate Data Online (CDO)**
   - Rich historical data
   - Requires API token (already configured)

4. **Automated Testing Pipeline**
   - GitHub Actions workflow
   - Daily validation of all endpoints
   - Data quality metrics

5. **Monitoring & Alerting**
   - CloudWatch dashboards
   - SNS alerts for ingestion failures
   - Data freshness metrics

---

**Document Version:**