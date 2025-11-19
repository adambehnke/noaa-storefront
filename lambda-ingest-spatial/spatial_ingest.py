#!/usr/bin/env python3
"""
NOAA Spatial Data Ingestion Script
Populates Bronze and Gold layers with spatial/metadata:
- NWS weather station metadata
- Forecast zone boundaries
- Geographic reference data
- Station capabilities

Usage:
    python3 spatial_ingest.py [--env dev]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import requests

# Configuration
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# AWS clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")


def fetch_all_stations(state: Optional[str] = None) -> Optional[Dict]:
    """Fetch all weather stations or stations by state"""
    url = f"{NWS_API_BASE}/stations"
    params = {}

    if state:
        params["state"] = state
        print(f"  Fetching stations for {state}...")
    else:
        print(f"  Fetching all weather stations...")

    try:
        response = requests.get(
            url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            if "features" in data:
                station_count = len(data["features"])
                print(f"    ✓ Retrieved {station_count} stations")
                return data
            else:
                print(f"    ⚠ No stations found")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching stations: {e}")
        return None


def fetch_forecast_zones(zone_type: str = "forecast") -> Optional[Dict]:
    """Fetch forecast zones"""
    url = f"{NWS_API_BASE}/zones/{zone_type}"

    print(f"  Fetching {zone_type} zones...")

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if "features" in data:
                zone_count = len(data["features"])
                print(f"    ✓ Retrieved {zone_count} zones")
                return data
            else:
                print(f"    ⚠ No zones found")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching zones: {e}")
        return None


def fetch_radar_stations() -> Optional[Dict]:
    """Fetch radar station metadata"""
    url = f"{NWS_API_BASE}/radar/stations"

    print(f"  Fetching radar stations...")

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "features" in data:
                radar_count = len(data["features"])
                print(f"    ✓ Retrieved {radar_count} radar stations")
                return data
            else:
                print(f"    ⚠ No radar stations found")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching radar stations: {e}")
        return None


def store_to_bronze(bucket: str, data: Dict, data_type: str, identifier: str):
    """Store raw spatial data to Bronze layer in S3"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    s3_key = f"bronze/spatial/{data_type}/date={date_str}/{identifier}_{timestamp}.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(data))
        print(f"    ✓ Stored to Bronze: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Bronze: {e}")
        return False


def aggregate_stations_to_gold(bucket: str, stations_data: Dict):
    """Aggregate station metadata and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not stations_data or "features" not in stations_data:
        return False

    features = stations_data["features"]

    # Extract and simplify station data
    stations_summary = []

    for feature in features:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])

        station = {
            "station_id": props.get("stationIdentifier", ""),
            "name": props.get("name", ""),
            "elevation": props.get("elevation", {}).get("value"),
            "elevation_unit": props.get("elevation", {}).get("unitCode", ""),
            "timezone": props.get("timeZone", ""),
        }

        # Extract coordinates
        if coords and len(coords) >= 2:
            station["longitude"] = coords[0]
            station["latitude"] = coords[1]
        else:
            station["longitude"] = None
            station["latitude"] = None

        stations_summary.append(station)

    aggregated = {
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "total_stations": len(stations_summary),
        "stations": stations_summary[:1000],  # Limit size for JSON
    }

    s3_key = f"gold/spatial/stations/date={date_str}/stations_summary.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(aggregated))
        print(f"    ✓ Stored stations to Gold: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing stations to Gold: {e}")
        return False


def aggregate_zones_to_gold(bucket: str, zones_data: Dict, zone_type: str):
    """Aggregate zone metadata and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not zones_data or "features" not in zones_data:
        return False

    features = zones_data["features"]

    # Extract and simplify zone data
    zones_summary = []

    for feature in features:
        props = feature.get("properties", {})

        zone = {
            "zone_id": props.get("id", ""),
            "name": props.get("name", ""),
            "state": props.get("state", ""),
            "zone_type": props.get("type", ""),
            "observation_stations": props.get("observationStations", [])[:5]
            if props.get("observationStations")
            else [],
        }

        zones_summary.append(zone)

    aggregated = {
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "zone_type": zone_type,
        "total_zones": len(zones_summary),
        "zones": zones_summary[:500],  # Limit size
    }

    s3_key = f"gold/spatial/zones/date={date_str}/zones_{zone_type}_summary.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(aggregated))
        print(f"    ✓ Stored zones to Gold: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing zones to Gold: {e}")
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
    parser = argparse.ArgumentParser(description="NOAA spatial data ingestion")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument(
        "--states",
        nargs="+",
        help="Specific states to process (default: all)",
    )
    args = parser.parse_args()

    env = args.env

    # Configuration
    bucket = f"noaa-federated-lake-899626030376-{env}"
    gold_db = f"noaa_gold_{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{'=' * 60}")
    print(f"NOAA Spatial Data Ingestion (Metadata)")
    print(f"{'=' * 60}")
    print(f"Environment: {env}")
    print(f"Target bucket: {bucket}")
    print(f"Gold database: {gold_db}")
    print(f"{'=' * 60}\n")

    success_count = 0

    # Fetch and store all stations
    print("\n--- Processing Weather Stations ---\n")
    stations_data = fetch_all_stations()
    if stations_data:
        store_to_bronze(bucket, stations_data, "stations", "national")
        aggregate_stations_to_gold(bucket, stations_data)
        success_count += 1
        time.sleep(1)

    # Fetch stations by state if specified
    if args.states:
        for state in args.states:
            state_stations = fetch_all_stations(state=state)
            if state_stations:
                store_to_bronze(bucket, state_stations, "stations", state)
                success_count += 1
                time.sleep(1)

    # Fetch and store forecast zones
    print("\n--- Processing Forecast Zones ---\n")
    forecast_zones = fetch_forecast_zones("forecast")
    if forecast_zones:
        store_to_bronze(bucket, forecast_zones, "zones", "forecast")
        aggregate_zones_to_gold(bucket, forecast_zones, "forecast")
        success_count += 1
        time.sleep(1)

    # Fetch and store fire weather zones
    print("\n--- Processing Fire Weather Zones ---\n")
    fire_zones = fetch_forecast_zones("fire")
    if fire_zones:
        store_to_bronze(bucket, fire_zones, "zones", "fire")
        aggregate_zones_to_gold(bucket, fire_zones, "fire")
        success_count += 1
        time.sleep(1)

    # Fetch and store radar stations
    print("\n--- Processing Radar Stations ---\n")
    radar_data = fetch_radar_stations()
    if radar_data:
        store_to_bronze(bucket, radar_data, "radar", "national")
        success_count += 1

    print(f"\n{'=' * 60}")
    print(f"Ingestion Summary")
    print(f"{'=' * 60}")
    print(f"Successfully processed: {success_count} metadata types")
    print(f"{'=' * 60}\n")

    # Refresh Athena tables
    print("Refreshing Athena tables...")

    # Create stations Gold table
    create_stations_table = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.spatial_stations (
        timestamp STRING,
        total_stations INT,
        stations ARRAY<STRUCT<
            station_id:STRING,
            name:STRING,
            elevation:DOUBLE,
            elevation_unit:STRING,
            timezone:STRING,
            longitude:DOUBLE,
            latitude:DOUBLE
        >>
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/spatial/stations/'
    """
    run_athena_query(gold_db, create_stations_table, athena_results_bucket)

    # Create zones Gold table
    create_zones_table = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.spatial_zones (
        timestamp STRING,
        zone_type STRING,
        total_zones INT,
        zones ARRAY<STRUCT<
            zone_id:STRING,
            name:STRING,
            state:STRING,
            zone_type:STRING,
            observation_stations:ARRAY<STRING>
        >>
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/spatial/zones/'
    """
    run_athena_query(gold_db, create_zones_table, athena_results_bucket)

    # Repair partitions
    run_athena_query(
        gold_db,
        f"MSCK REPAIR TABLE {gold_db}.spatial_stations",
        athena_results_bucket,
    )
    run_athena_query(
        gold_db, f"MSCK REPAIR TABLE {gold_db}.spatial_zones", athena_results_bucket
    )

    print("\n✅ Spatial data ingestion complete!")
    print(f"\nData products ingested:")
    print(f"  ✓ Weather Station Metadata")
    print(f"  ✓ Forecast Zones")
    print(f"  ✓ Fire Weather Zones")
    print(f"  ✓ Radar Station Locations")
    print(f"\nTo query the data:")
    print(f"  SELECT * FROM {gold_db}.spatial_stations LIMIT 10;")
    print(f"  SELECT * FROM {gold_db}.spatial_zones LIMIT 10;")
    print()


if __name__ == "__main__":
    main()
