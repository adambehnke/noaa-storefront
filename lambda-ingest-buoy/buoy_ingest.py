#!/usr/bin/env python3
"""
NDBC Buoy Data Ingestion Script
Populates Bronze and Gold layers with buoy observation data:
- Wave height and period
- Wind speed and direction
- Air and water temperature
- Atmospheric pressure
- Other marine conditions

Usage:
    python3 buoy_ingest.py [--env dev] [--hours 24]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
import requests

# Configuration
NDBC_REALTIME_BASE = "https://www.ndbc.noaa.gov/data/realtime2"
NDBC_LATEST_OBS = "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# Active buoy stations across US coastal waters
BUOY_STATIONS = {
    "46042": {
        "name": "Monterey Bay",
        "state": "CA",
        "region": "West Coast",
        "lat": 36.785,
        "lon": -122.398,
    },
    "46026": {
        "name": "San Francisco",
        "state": "CA",
        "region": "West Coast",
        "lat": 37.759,
        "lon": -122.833,
    },
    "46011": {
        "name": "Santa Maria",
        "state": "CA",
        "region": "West Coast",
        "lat": 34.868,
        "lon": -120.862,
    },
    "44018": {
        "name": "Cape Cod",
        "state": "MA",
        "region": "Northeast",
        "lat": 42.128,
        "lon": -69.590,
    },
    "44025": {
        "name": "Long Island",
        "state": "NY",
        "region": "Northeast",
        "lat": 40.251,
        "lon": -73.164,
    },
    "44009": {
        "name": "Delaware Bay",
        "state": "DE",
        "region": "Mid-Atlantic",
        "lat": 38.457,
        "lon": -74.702,
    },
    "41002": {
        "name": "South Hatteras",
        "state": "NC",
        "region": "Southeast",
        "lat": 31.759,
        "lon": -74.936,
    },
    "41010": {
        "name": "Canaveral East",
        "state": "FL",
        "region": "Southeast",
        "lat": 28.878,
        "lon": -78.485,
    },
    "42040": {
        "name": "Luke Offshore",
        "state": "LA",
        "region": "Gulf Coast",
        "lat": 29.182,
        "lon": -88.226,
    },
    "42019": {
        "name": "Freeport",
        "state": "TX",
        "region": "Gulf Coast",
        "lat": 27.907,
        "lon": -95.352,
    },
    "51004": {
        "name": "Southeast Hawaii",
        "state": "HI",
        "region": "Pacific",
        "lat": 17.507,
        "lon": -152.373,
    },
    "51001": {
        "name": "Northwest Hawaii",
        "state": "HI",
        "region": "Pacific",
        "lat": 23.445,
        "lon": -162.075,
    },
}

# AWS clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")


def parse_ndbc_line(line: str, headers: List[str]) -> Optional[Dict]:
    """Parse a single line of NDBC data"""
    try:
        # Split by whitespace
        values = line.strip().split()

        if len(values) != len(headers):
            return None

        # Create dict from headers and values
        data = {}
        for i, header in enumerate(headers):
            value = values[i]

            # Handle missing/invalid values
            if value == "MM":
                data[header] = None
            else:
                try:
                    # Try to convert to float
                    data[header] = float(value)
                except ValueError:
                    # Keep as string if not a number
                    data[header] = value

        return data

    except Exception as e:
        print(f"    ⚠ Error parsing line: {e}")
        return None


def fetch_buoy_data(station_id: str) -> Optional[Dict]:
    """Fetch real-time buoy data from NDBC"""
    url = f"{NDBC_REALTIME_BASE}/{station_id}.txt"

    try:
        print(f"  Fetching buoy data for {station_id}...")
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)

        if response.status_code == 200:
            lines = response.text.strip().split("\n")

            if len(lines) < 3:
                print(f"    ⚠ Insufficient data for station {station_id}")
                return None

            # First line is headers, second line is units
            headers_line = lines[0].strip()
            units_line = lines[1].strip()

            # Parse headers (handle multiple spaces)
            headers = re.split(r"\s+", headers_line.replace("#", "").strip())

            # Parse data lines (skip header and units)
            data_records = []
            for line in lines[2:]:
                if line.strip():
                    record = parse_ndbc_line(line, headers)
                    if record:
                        data_records.append(record)

            if data_records:
                print(f"    ✓ Retrieved {len(data_records)} buoy observations")
                return {
                    "station_id": station_id,
                    "headers": headers,
                    "units": re.split(r"\s+", units_line.replace("#", "").strip()),
                    "data": data_records,
                    "fetched_at": datetime.utcnow().isoformat(),
                }
            else:
                print(f"    ⚠ No valid data records for station {station_id}")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching buoy data: {e}")
        return None


def store_to_bronze(bucket: str, data: Dict, station_id: str):
    """Store raw buoy data to Bronze layer in S3"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    s3_key = f"bronze/buoy/date={date_str}/station_{station_id}_{timestamp}.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(data))
        print(f"    ✓ Stored to Bronze: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Bronze: {e}")
        return False


def aggregate_to_gold(
    bucket: str, station_id: str, station_info: Dict, buoy_data: Dict
):
    """Aggregate buoy data and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Extract data records
    records = buoy_data.get("data", [])

    if not records:
        print(f"    ⚠ No records to aggregate")
        return False

    # Calculate aggregations for various measurements
    aggregated = {
        "station_id": station_id,
        "station_name": station_info["name"],
        "state": station_info["state"],
        "region": station_info["region"],
        "latitude": station_info["lat"],
        "longitude": station_info["lon"],
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "observation_count": len(records),
    }

    # Wave height (WVHT - meters)
    wave_heights = [r.get("WVHT") for r in records if r.get("WVHT") is not None]
    if wave_heights:
        aggregated["avg_wave_height_m"] = sum(wave_heights) / len(wave_heights)
        aggregated["max_wave_height_m"] = max(wave_heights)
        aggregated["min_wave_height_m"] = min(wave_heights)
    else:
        aggregated["avg_wave_height_m"] = None
        aggregated["max_wave_height_m"] = None
        aggregated["min_wave_height_m"] = None

    # Dominant wave period (DPD - seconds)
    wave_periods = [r.get("DPD") for r in records if r.get("DPD") is not None]
    if wave_periods:
        aggregated["avg_wave_period_sec"] = sum(wave_periods) / len(wave_periods)
    else:
        aggregated["avg_wave_period_sec"] = None

    # Wind speed (WSPD - m/s)
    wind_speeds = [r.get("WSPD") for r in records if r.get("WSPD") is not None]
    if wind_speeds:
        aggregated["avg_wind_speed_mps"] = sum(wind_speeds) / len(wind_speeds)
        aggregated["max_wind_speed_mps"] = max(wind_speeds)
    else:
        aggregated["avg_wind_speed_mps"] = None
        aggregated["max_wind_speed_mps"] = None

    # Gust speed (GST - m/s)
    gust_speeds = [r.get("GST") for r in records if r.get("GST") is not None]
    if gust_speeds:
        aggregated["max_gust_speed_mps"] = max(gust_speeds)
    else:
        aggregated["max_gust_speed_mps"] = None

    # Air temperature (ATMP - Celsius)
    air_temps = [r.get("ATMP") for r in records if r.get("ATMP") is not None]
    if air_temps:
        aggregated["avg_air_temp_c"] = sum(air_temps) / len(air_temps)
        aggregated["max_air_temp_c"] = max(air_temps)
        aggregated["min_air_temp_c"] = min(air_temps)
    else:
        aggregated["avg_air_temp_c"] = None
        aggregated["max_air_temp_c"] = None
        aggregated["min_air_temp_c"] = None

    # Water temperature (WTMP - Celsius)
    water_temps = [r.get("WTMP") for r in records if r.get("WTMP") is not None]
    if water_temps:
        aggregated["avg_water_temp_c"] = sum(water_temps) / len(water_temps)
        aggregated["max_water_temp_c"] = max(water_temps)
        aggregated["min_water_temp_c"] = min(water_temps)
    else:
        aggregated["avg_water_temp_c"] = None
        aggregated["max_water_temp_c"] = None
        aggregated["min_water_temp_c"] = None

    # Atmospheric pressure (PRES - hPa)
    pressures = [r.get("PRES") for r in records if r.get("PRES") is not None]
    if pressures:
        aggregated["avg_pressure_hpa"] = sum(pressures) / len(pressures)
    else:
        aggregated["avg_pressure_hpa"] = None

    # Wave direction (WDIR - degrees)
    wave_dirs = [r.get("WDIR") for r in records if r.get("WDIR") is not None]
    if wave_dirs:
        aggregated["predominant_wave_dir_deg"] = sum(wave_dirs) / len(
            wave_dirs
        )  # Simple average
    else:
        aggregated["predominant_wave_dir_deg"] = None

    # Store to Gold layer
    s3_key = f"gold/buoy/date={date_str}/station_{station_id}_aggregated.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(aggregated))
        print(f"    ✓ Stored to Gold: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Gold: {e}")
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
    parser = argparse.ArgumentParser(description="NDBC buoy data ingestion")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument(
        "--stations",
        nargs="+",
        help="Specific station IDs to process (default: all)",
    )
    args = parser.parse_args()

    env = args.env
    stations_to_process = (
        {k: v for k, v in BUOY_STATIONS.items() if k in args.stations}
        if args.stations
        else BUOY_STATIONS
    )

    # Configuration
    bucket = f"noaa-federated-lake-899626030376-{env}"
    gold_db = f"noaa_gold_{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{'=' * 60}")
    print(f"NOAA Buoy Data Ingestion (NDBC)")
    print(f"{'=' * 60}")
    print(f"Environment: {env}")
    print(f"Target bucket: {bucket}")
    print(f"Gold database: {gold_db}")
    print(f"Stations to process: {len(stations_to_process)}")
    print(f"{'=' * 60}\n")

    success_count = 0
    total_count = len(stations_to_process)

    for station_id, station_info in stations_to_process.items():
        print(
            f"\n[{success_count + 1}/{total_count}] Processing buoy {station_id} ({station_info['name']}, {station_info['state']})..."
        )

        # Fetch buoy data
        buoy_data = fetch_buoy_data(station_id)

        if buoy_data:
            # Store to Bronze
            store_to_bronze(bucket, buoy_data, station_id)

            # Aggregate to Gold
            aggregate_to_gold(bucket, station_id, station_info, buoy_data)

            success_count += 1
        else:
            print(f"  ⚠ No data available for buoy {station_id}")

    print(f"\n{'=' * 60}")
    print(f"Ingestion Summary")
    print(f"{'=' * 60}")
    print(f"Successfully processed: {success_count}/{total_count} buoys")
    print(f"{'=' * 60}\n")

    # Refresh Athena tables
    print("Refreshing Athena tables...")

    # Create Gold table if not exists
    create_table_sql = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.buoy_aggregated (
        station_id STRING,
        station_name STRING,
        state STRING,
        region STRING,
        latitude DOUBLE,
        longitude DOUBLE,
        timestamp STRING,
        observation_count INT,
        avg_wave_height_m DOUBLE,
        max_wave_height_m DOUBLE,
        min_wave_height_m DOUBLE,
        avg_wave_period_sec DOUBLE,
        avg_wind_speed_mps DOUBLE,
        max_wind_speed_mps DOUBLE,
        max_gust_speed_mps DOUBLE,
        avg_air_temp_c DOUBLE,
        max_air_temp_c DOUBLE,
        min_air_temp_c DOUBLE,
        avg_water_temp_c DOUBLE,
        max_water_temp_c DOUBLE,
        min_water_temp_c DOUBLE,
        avg_pressure_hpa DOUBLE,
        predominant_wave_dir_deg DOUBLE
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/buoy/'
    """

    run_athena_query(gold_db, create_table_sql, athena_results_bucket)

    # Repair partitions
    repair_sql = f"MSCK REPAIR TABLE {gold_db}.buoy_aggregated"
    run_athena_query(gold_db, repair_sql, athena_results_bucket)

    print("\n✅ Buoy data ingestion complete!")
    print(f"\nData products ingested:")
    print(f"  ✓ Wave Height & Period")
    print(f"  ✓ Wind Speed & Direction")
    print(f"  ✓ Air & Water Temperature")
    print(f"  ✓ Atmospheric Pressure")
    print(f"  ✓ Marine Conditions")
    print(f"\nTo query the data:")
    print(f"  SELECT * FROM {gold_db}.buoy_aggregated LIMIT 10;")
    print()


if __name__ == "__main__":
    main()
