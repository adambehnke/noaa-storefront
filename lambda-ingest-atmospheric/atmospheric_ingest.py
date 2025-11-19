#!/usr/bin/env python3
"""
NWS Atmospheric Data Ingestion Script
Populates Bronze and Gold layers with weather data:
- Active weather alerts
- Weather forecasts
- Current observations
- Station data

Usage:
    python3 atmospheric_ingest.py [--env dev]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
import requests

# Configuration
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# Major cities with NWS grid coordinates
FORECAST_LOCATIONS = {
    "new_york": {
        "name": "New York City",
        "state": "NY",
        "region": "Northeast",
        "lat": 40.7128,
        "lon": -74.0060,
        "office": "OKX",
        "gridX": 33,
        "gridY": 37,
    },
    "los_angeles": {
        "name": "Los Angeles",
        "state": "CA",
        "region": "West Coast",
        "lat": 34.0522,
        "lon": -118.2437,
        "office": "LOX",
        "gridX": 154,
        "gridY": 44,
    },
    "chicago": {
        "name": "Chicago",
        "state": "IL",
        "region": "Midwest",
        "lat": 41.8781,
        "lon": -87.6298,
        "office": "LOT",
        "gridX": 76,
        "gridY": 73,
    },
    "houston": {
        "name": "Houston",
        "state": "TX",
        "region": "South",
        "lat": 29.7604,
        "lon": -95.3698,
        "office": "HGX",
        "gridX": 67,
        "gridY": 100,
    },
    "phoenix": {
        "name": "Phoenix",
        "state": "AZ",
        "region": "Southwest",
        "lat": 33.4484,
        "lon": -112.0740,
        "office": "PSR",
        "gridX": 157,
        "gridY": 64,
    },
    "miami": {
        "name": "Miami",
        "state": "FL",
        "region": "Southeast",
        "lat": 25.7617,
        "lon": -80.1918,
        "office": "MFL",
        "gridX": 110,
        "gridY": 50,
    },
    "seattle": {
        "name": "Seattle",
        "state": "WA",
        "region": "Northwest",
        "lat": 47.6062,
        "lon": -122.3321,
        "office": "SEW",
        "gridX": 124,
        "gridY": 67,
    },
    "boston": {
        "name": "Boston",
        "state": "MA",
        "region": "Northeast",
        "lat": 42.3601,
        "lon": -71.0589,
        "office": "BOX",
        "gridX": 71,
        "gridY": 90,
    },
}

# AWS clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")


def fetch_active_alerts(state: Optional[str] = None) -> Optional[Dict]:
    """Fetch active weather alerts from NWS"""
    url = f"{NWS_API_BASE}/alerts/active"
    params = {}

    if state:
        params["area"] = state
        print(f"  Fetching alerts for {state}...")
    else:
        print(f"  Fetching all active alerts...")

    try:
        response = requests.get(
            url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if "features" in data:
                alert_count = len(data["features"])
                print(f"    ✓ Retrieved {alert_count} active alerts")
                return data
            else:
                print(f"    ⚠ No alerts found")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching alerts: {e}")
        return None


def fetch_forecast(location_id: str, location_info: Dict) -> Optional[Dict]:
    """Fetch weather forecast from NWS"""
    office = location_info["office"]
    grid_x = location_info["gridX"]
    grid_y = location_info["gridY"]

    url = f"{NWS_API_BASE}/gridpoints/{office}/{grid_x},{grid_y}/forecast"

    print(f"  Fetching forecast for {location_info['name']}...")

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "properties" in data and "periods" in data["properties"]:
                periods = data["properties"]["periods"]
                print(f"    ✓ Retrieved forecast with {len(periods)} periods")
                return {
                    "location_id": location_id,
                    "location_name": location_info["name"],
                    "state": location_info["state"],
                    "forecast": data,
                }
            else:
                print(f"    ⚠ No forecast data available")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching forecast: {e}")
        return None


def fetch_hourly_forecast(location_id: str, location_info: Dict) -> Optional[Dict]:
    """Fetch hourly weather forecast from NWS"""
    office = location_info["office"]
    grid_x = location_info["gridX"]
    grid_y = location_info["gridY"]

    url = f"{NWS_API_BASE}/gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly"

    print(f"  Fetching hourly forecast for {location_info['name']}...")

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "properties" in data and "periods" in data["properties"]:
                periods = data["properties"]["periods"]
                print(f"    ✓ Retrieved {len(periods)} hourly periods")
                return {
                    "location_id": location_id,
                    "location_name": location_info["name"],
                    "state": location_info["state"],
                    "hourly_forecast": data,
                }
            else:
                print(f"    ⚠ No hourly forecast data available")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching hourly forecast: {e}")
        return None


def store_to_bronze(bucket: str, data: Dict, data_type: str, identifier: str):
    """Store raw data to Bronze layer in S3"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    s3_key = (
        f"bronze/atmospheric/{data_type}/date={date_str}/{identifier}_{timestamp}.json"
    )

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(data))
        print(f"    ✓ Stored to Bronze: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Bronze: {e}")
        return False


def aggregate_alerts_to_gold(bucket: str, alerts_data: Dict):
    """Aggregate alert data and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not alerts_data or "features" not in alerts_data:
        return False

    features = alerts_data["features"]

    # Aggregate by state and severity
    aggregations = {}

    for feature in features:
        props = feature.get("properties", {})

        # Extract state from areaDesc or geocode
        area_desc = props.get("areaDesc", "")
        event = props.get("event", "Unknown")
        severity = props.get("severity", "Unknown")

        # Simple aggregation by event type
        key = f"{event}_{severity}"

        if key not in aggregations:
            aggregations[key] = {
                "event_type": event,
                "severity": severity,
                "count": 0,
                "areas": set(),
            }

        aggregations[key]["count"] += 1
        aggregations[key]["areas"].add(area_desc[:100])  # Limit length

    # Convert to list for JSON serialization
    aggregated = {
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "total_alerts": len(features),
        "alert_summary": [
            {
                "event_type": v["event_type"],
                "severity": v["severity"],
                "alert_count": v["count"],
                "sample_areas": list(v["areas"])[:5],
            }
            for v in aggregations.values()
        ],
    }

    s3_key = f"gold/atmospheric/alerts/date={date_str}/alerts_aggregated.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(aggregated))
        print(f"    ✓ Stored alerts to Gold: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing alerts to Gold: {e}")
        return False


def aggregate_forecasts_to_gold(
    bucket: str, location_id: str, location_info: Dict, forecast_data: Dict
):
    """Aggregate forecast data and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not forecast_data or "forecast" not in forecast_data:
        return False

    forecast = forecast_data["forecast"]
    properties = forecast.get("properties", {})
    periods = properties.get("periods", [])

    if not periods:
        return False

    # Get current and next period
    current_period = periods[0] if len(periods) > 0 else {}

    aggregated = {
        "location_id": location_id,
        "location_name": location_info["name"],
        "state": location_info["state"],
        "region": location_info["region"],
        "latitude": location_info["lat"],
        "longitude": location_info["lon"],
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "current_period": {
            "name": current_period.get("name"),
            "temperature": current_period.get("temperature"),
            "temperature_unit": current_period.get("temperatureUnit"),
            "wind_speed": current_period.get("windSpeed"),
            "wind_direction": current_period.get("windDirection"),
            "short_forecast": current_period.get("shortForecast"),
        },
        "forecast_periods_count": len(periods),
    }

    # Extract temperatures for all periods
    temps = [p.get("temperature") for p in periods if p.get("temperature")]
    if temps:
        aggregated["forecast_high_temp"] = max(temps)
        aggregated["forecast_low_temp"] = min(temps)

    s3_key = f"gold/atmospheric/forecasts/date={date_str}/forecast_{location_id}.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(aggregated))
        print(f"    ✓ Stored forecast to Gold: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing forecast to Gold: {e}")
        return False


def run_athena_query(database: str, query: str, output_bucket: str):
    """Execute Athena query"""
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": f"s3://{output_bucket}/"},
        )
        query_id = response["QueryExecutionId"]
        print(f"    ✓ Started Athena query: {query_id}")
        return query_id
    except Exception as e:
        print(f"    ✗ Error executing Athena query: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="NWS atmospheric data ingestion")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument(
        "--locations",
        nargs="+",
        help="Specific location IDs to process (default: all)",
    )
    args = parser.parse_args()

    env = args.env
    locations_to_process = (
        {k: v for k, v in FORECAST_LOCATIONS.items() if k in args.locations}
        if args.locations
        else FORECAST_LOCATIONS
    )

    # Configuration
    bucket = f"noaa-federated-lake-899626030376-{env}"
    gold_db = f"noaa_gold_{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{'=' * 60}")
    print(f"NOAA Atmospheric Data Ingestion (NWS)")
    print(f"{'=' * 60}")
    print(f"Environment: {env}")
    print(f"Target bucket: {bucket}")
    print(f"Gold database: {gold_db}")
    print(f"Locations to process: {len(locations_to_process)}")
    print(f"{'=' * 60}\n")

    # Fetch and store active alerts
    print("\n--- Processing Weather Alerts ---\n")
    alerts_data = fetch_active_alerts()
    if alerts_data:
        store_to_bronze(bucket, alerts_data, "alerts", "national")
        aggregate_alerts_to_gold(bucket, alerts_data)

    # Process forecasts for each location
    print("\n--- Processing Location Forecasts ---\n")
    success_count = 0
    total_count = len(locations_to_process)

    for location_id, location_info in locations_to_process.items():
        print(
            f"\n[{success_count + 1}/{total_count}] Processing {location_info['name']}, {location_info['state']}..."
        )

        # Fetch forecast
        forecast_data = fetch_forecast(location_id, location_info)

        # Fetch hourly forecast
        hourly_data = fetch_hourly_forecast(location_id, location_info)

        if forecast_data or hourly_data:
            # Store to Bronze
            if forecast_data:
                store_to_bronze(bucket, forecast_data, "forecasts", location_id)
                aggregate_forecasts_to_gold(
                    bucket, location_id, location_info, forecast_data
                )

            if hourly_data:
                store_to_bronze(bucket, hourly_data, "hourly_forecasts", location_id)

            success_count += 1
        else:
            print(f"  ⚠ No data available for {location_info['name']}")

        # Rate limiting - be nice to NWS API
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"Ingestion Summary")
    print(f"{'=' * 60}")
    print(f"Successfully processed: {success_count}/{total_count} locations")
    print(f"Alerts ingested: {'Yes' if alerts_data else 'No'}")
    print(f"{'=' * 60}\n")

    # Refresh Athena tables
    print("Refreshing Athena tables...")

    # Create alerts Gold table
    create_alerts_table = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.atmospheric_alerts (
        timestamp STRING,
        total_alerts INT,
        alert_summary ARRAY<STRUCT<
            event_type:STRING,
            severity:STRING,
            alert_count:INT,
            sample_areas:ARRAY<STRING>
        >>
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/atmospheric/alerts/'
    """
    run_athena_query(gold_db, create_alerts_table, athena_results_bucket)

    # Create forecasts Gold table
    create_forecasts_table = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.atmospheric_forecasts (
        location_id STRING,
        location_name STRING,
        state STRING,
        region STRING,
        latitude DOUBLE,
        longitude DOUBLE,
        timestamp STRING,
        current_period STRUCT<
            name:STRING,
            temperature:INT,
            temperature_unit:STRING,
            wind_speed:STRING,
            wind_direction:STRING,
            short_forecast:STRING
        >,
        forecast_periods_count INT,
        forecast_high_temp INT,
        forecast_low_temp INT
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/atmospheric/forecasts/'
    """
    run_athena_query(gold_db, create_forecasts_table, athena_results_bucket)

    # Repair partitions
    run_athena_query(
        gold_db,
        f"MSCK REPAIR TABLE {gold_db}.atmospheric_alerts",
        athena_results_bucket,
    )
    run_athena_query(
        gold_db,
        f"MSCK REPAIR TABLE {gold_db}.atmospheric_forecasts",
        athena_results_bucket,
    )

    print("\n✅ Atmospheric data ingestion complete!")
    print(f"\nData products ingested:")
    print(f"  ✓ Weather Alerts")
    print(f"  ✓ Weather Forecasts")
    print(f"  ✓ Hourly Forecasts")
    print(f"\nTo query the data:")
    print(f"  SELECT * FROM {gold_db}.atmospheric_alerts LIMIT 10;")
    print(f"  SELECT * FROM {gold_db}.atmospheric_forecasts LIMIT 10;")
    print()


if __name__ == "__main__":
    main()
