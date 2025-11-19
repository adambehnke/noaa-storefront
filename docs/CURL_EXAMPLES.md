# NOAA Endpoint Testing - Quick Reference Guide

**Purpose:** Ready-to-use curl commands for testing each NOAA endpoint and the federated API

---

## Table of Contents

1. [Oceanic Pond (CO-OPS)](#oceanic-pond-co-ops)
2. [Atmospheric Pond (NWS)](#atmospheric-pond-nws)
3. [Buoy Pond (NDBC)](#buoy-pond-ndbc)
4. [Climate Pond (CDO)](#climate-pond-cdo)
5. [Federated API Queries](#federated-api-queries)
6. [AWS Data Lake Queries](#aws-data-lake-queries)

---

## Oceanic Pond (CO-OPS)

### Water Temperature

**San Francisco Bay:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

**Date Range:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&begin_date=20240101%2000:00&end_date=20240101%2023:59&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

**Multiple Stations:**
```bash
# New York Harbor (The Battery)
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=8518750&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"

# Seattle
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9447130&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"

# Boston
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=8443970&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

---

### Water Levels

**Current Water Level:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&station=9414290&date=latest&datum=MLLW&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

**24-Hour History:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&station=9414290&begin_date=20240101%2000:00&end_date=20240101%2023:59&datum=MLLW&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

---

### Tide Predictions

**High/Low Tides:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=predictions&station=9414290&begin_date=20240101&end_date=20240102&datum=MLLW&time_zone=GMT&units=metric&format=json&interval=hilo&application=NOAA_Federated_DataLake"
```

**Hourly Predictions:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=predictions&station=9414290&begin_date=20240101&end_date=20240102&datum=MLLW&time_zone=GMT&units=metric&format=json&interval=h&application=NOAA_Federated_DataLake"
```

---

### Currents

**Current Speed & Direction:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=currents&station=PUG1515&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake"
```

---

### Salinity

**Water Salinity:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=salinity&station=8454000&date=latest&time_zone=GMT&format=json&application=NOAA_Federated_DataLake"
```

---

### Station Information

**List Available Stations:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels"
```

**Station Metadata:**
```bash
curl -X GET "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/9414290.json"
```

---

## Atmospheric Pond (NWS)

### Active Weather Alerts

**All Active Alerts:**
```bash
curl -X GET "https://api.weather.gov/alerts/active" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**By State:**
```bash
# California
curl -X GET "https://api.weather.gov/alerts/active?area=CA" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Texas
curl -X GET "https://api.weather.gov/alerts/active?area=TX" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Florida
curl -X GET "https://api.weather.gov/alerts/active?area=FL" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**By Severity:**
```bash
curl -X GET "https://api.weather.gov/alerts/active?severity=severe" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**By Event Type:**
```bash
curl -X GET "https://api.weather.gov/alerts/active?event=Tornado%20Warning" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

---

### Current Weather & Forecast

**Get Grid Coordinates for Location:**
```bash
# New York City
curl -X GET "https://api.weather.gov/points/40.7128,-74.0060" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Los Angeles
curl -X GET "https://api.weather.gov/points/34.0522,-118.2437" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Chicago
curl -X GET "https://api.weather.gov/points/41.8781,-87.6298" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Current Conditions (Grid Point):**
```bash
# New York City (OKX 33,37)
curl -X GET "https://api.weather.gov/gridpoints/OKX/33,37" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# Los Angeles (LOX 154,44)
curl -X GET "https://api.weather.gov/gridpoints/LOX/154,44" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**7-Day Forecast:**
```bash
curl -X GET "https://api.weather.gov/gridpoints/OKX/33,37/forecast" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Hourly Forecast:**
```bash
curl -X GET "https://api.weather.gov/gridpoints/OKX/33,37/forecast/hourly" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

---

### Weather Stations

**List All Stations:**
```bash
curl -X GET "https://api.weather.gov/stations" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Stations by State:**
```bash
curl -X GET "https://api.weather.gov/stations?state=CA" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Latest Observation from Station:**
```bash
# JFK Airport
curl -X GET "https://api.weather.gov/stations/KJFK/observations/latest" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"

# LAX Airport
curl -X GET "https://api.weather.gov/stations/KLAX/observations/latest" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

---

### Forecast Zones

**List Forecast Zones:**
```bash
curl -X GET "https://api.weather.gov/zones/forecast" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

**Zone by ID:**
```bash
curl -X GET "https://api.weather.gov/zones/forecast/CAZ006" \
  -H "User-Agent: NOAA_Federated_DataLake/1.0"
```

---

## Buoy Pond (NDBC)

### Latest Buoy Observations

**All Active Buoys:**
```bash
curl -X GET "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"
```

**Specific Buoy (Real-time):**
```bash
# Monterey Bay (46042)
curl -X GET "https://www.ndbc.noaa.gov/data/realtime2/46042.txt"

# Cape Cod (44018)
curl -X GET "https://www.ndbc.noaa.gov/data/realtime2/44018.txt"

# San Francisco Bay (46026)
curl -X GET "https://www.ndbc.noaa.gov/data/realtime2/46026.txt"
```

**Historical Data:**
```bash
# Monthly summary
curl -X GET "https://www.ndbc.noaa.gov/data/historical/stdmet/46042h2024.txt.gz"
```

---

## Climate Pond (CDO)

**Note:** Requires API token from https://www.ncdc.noaa.gov/cdo-web/token

### Datasets

**List Available Datasets:**
```bash
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets" \
  -H "token: YOUR_CDO_TOKEN"
```

---

### Daily Climate Data

**Temperature & Precipitation:**
```bash
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&stationid=GHCND:USW00094728&startdate=2024-01-01&enddate=2024-01-31&limit=1000" \
  -H "token: YOUR_CDO_TOKEN"
```

**Specific Data Types:**
```bash
# Maximum temperature only
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&stationid=GHCND:USW00094728&startdate=2024-01-01&enddate=2024-01-31&datatypeid=TMAX" \
  -H "token: YOUR_CDO_TOKEN"

# Precipitation
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&stationid=GHCND:USW00094728&startdate=2024-01-01&enddate=2024-01-31&datatypeid=PRCP" \
  -H "token: YOUR_CDO_TOKEN"
```

---

### Stations

**List Climate Stations:**
```bash
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/stations?limit=100" \
  -H "token: YOUR_CDO_TOKEN"
```

**Stations by Location:**
```bash
curl -X GET "https://www.ncdc.noaa.gov/cdo-web/api/v2/stations?locationid=FIPS:06&limit=100" \
  -H "token: YOUR_CDO_TOKEN"
```

---

## Federated API Queries

**Base URL:** `https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask`

### Single-Pond Queries

**Oceanic Query:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the water temperature in San Francisco?"
  }'
```

**Atmospheric Query:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the current weather in New York City?"
  }'
```

**Weather Alerts Query:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Are there any severe weather warnings in California?"
  }'
```

---

### Multi-Pond Queries

**Weather + Ocean:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather in San Francisco and what is the water temperature in the bay?"
  }'
```

**Multi-Location:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the water temperatures along the California coast?"
  }'
```

**Regional Overview:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Give me a weather overview for the Pacific Northwest"
  }'
```

---

### Multiple Questions

**Combined Query:**
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the weather in Boston? What are the water levels in Boston Harbor? Are there any alerts in Massachusetts?"
  }'
```

---

### Formatted Output

**Pretty Print with jq:**
```bash
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the water temperature in San Francisco?"
  }' | jq '.'
```

**Extract Just the Answer:**
```bash
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the water temperature in San Francisco?"
  }' | jq -r '.answer'
```

**Extract Data Sources:**
```bash
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the water temperature in San Francisco?"
  }' | jq '.data_sources'
```

---

## AWS Data Lake Queries

### S3 Bronze Layer

**List Recent Oceanic Data:**
```bash
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/ --recursive | tail -20
```

**Download Sample File:**
```bash
aws s3 cp s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/date=2024-01-01/station_9414290_20240101_120000.json ./sample.json
```

**View File Content:**
```bash
aws s3 cp s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/date=2024-01-01/station_9414290_20240101_120000.json - | jq '.'
```

---

### S3 Gold Layer

**List Gold Data:**
```bash
aws s3 ls s3://noaa-federated-lake-899626030376-dev/gold/oceanic/ --recursive
```

---

### Athena Queries

**Start Query:**
```bash
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.oceanic_aggregated ORDER BY date DESC LIMIT 10" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

**Get Query Results:**
```bash
# Replace QUERY_EXECUTION_ID with actual ID from previous command
aws athena get-query-results \
  --query-execution-id QUERY_EXECUTION_ID \
  --output json | jq '.ResultSet.Rows'
```

**Show Tables:**
```bash
aws athena start-query-execution \
  --query-string "SHOW TABLES IN noaa_gold_dev" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

**Describe Table:**
```bash
aws athena start-query-execution \
  --query-string "DESCRIBE noaa_gold_dev.oceanic_aggregated" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

---

## Complete Test Flow

### End-to-End Validation

```bash
#!/bin/bash
# Complete test of one endpoint through all layers

echo "=== Step 1: Query NOAA API Directly ==="
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&date=latest&time_zone=GMT&units=metric&format=json&application=NOAA_Federated_DataLake" | jq '.data[0]'

echo ""
echo "=== Step 2: Check Bronze Layer ==="
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/ --recursive | tail -5

echo ""
echo "=== Step 3: Query Gold Layer ==="
# Note: This is async, need to wait for results
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT station_id, station_name, avg_water_temp, date FROM noaa_gold_dev.oceanic_aggregated WHERE station_id = '9414290' ORDER BY date DESC LIMIT 1" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/ \
  --output text --query 'QueryExecutionId')
echo "Athena Query ID: $QUERY_ID"

echo ""
echo "=== Step 4: Query via Federated API ==="
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in San Francisco?"}' | jq '.'

echo ""
echo "=== Test Complete ==="
```

---

## Troubleshooting Commands

### Check Lambda Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/noaa-enhanced-handler-dev --follow

# Get recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/noaa-enhanced-handler-dev \
  --filter-pattern "ERROR" \
  --max-items 20
```

### Invoke Lambda Directly

```bash
aws lambda invoke \
  --function-name noaa-enhanced-handler-dev \
  --payload '{"body": "{\"question\": \"test\"}"}' \
  response.json

cat response.json | jq '.'
```

### Check EventBridge Schedule

```bash
aws events list-rules --name-prefix noaa-ingest
```

### Manually Trigger Ingestion

```bash
aws lambda invoke \
  --function-name noaa-ingest-oceanic-dev \
  --payload '{"hours_back": 24, "env": "dev"}' \
  output.json
```

---

## Station Reference

### Popular CO-OPS Stations

| Station ID | Location | Region |
|------------|----------|--------|
| 9414290 | San Francisco, CA | West Coast |
| 9447130 | Seattle, WA | Northwest |
| 8518750 | The Battery, NY | Northeast |
| 8443970 | Boston, MA | Northeast |
| 8670870 | Fort Pulaski, GA | Southeast |
| 8723214 | Virginia Key, FL | Southeast |
| 8729108 | Panama City, FL | Gulf Coast |
| 8760922 | Corpus Christi, TX | Gulf Coast |

### Popular NDBC Buoys

| Buoy ID | Location | Data Types |
|---------|----------|------------|
| 46042 | Monterey Bay, CA | Waves, Wind, Temp |
| 46026 | San Francisco, CA | Waves, Wind, Temp |
| 44018 | Cape Cod, MA | Waves, Wind, Temp |
| 42040 | Gulf of Mexico | Waves, Wind, Temp |
| 51004 | Southeast Hawaii | Waves, Wind, Temp |

---

**Last Updated:** 2024  
**Maintained by:** NOAA Federated Data Lake Team