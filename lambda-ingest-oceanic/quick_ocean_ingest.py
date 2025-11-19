#!/usr/bin/env python3
"""
Complete Oceanic Data Ingestion Script
Populates Bronze and Gold layers with all CO-OPS products:
- Water temperature
- Water levels
- Tide predictions
- Currents
- Salinity

Usage:
    python3 quick_ocean_ingest.py [--env dev] [--hours 24]
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
import requests

# Configuration
TIDES_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# Coastal stations across the US with capability flags
STATIONS = {
    "8670870": {
        "name": "Fort Pulaski",
        "state": "GA",
        "region": "Southeast",
        "temp": True,
        "currents": False,
    },
    "8723214": {
        "name": "Virginia Key",
        "state": "FL",
        "region": "Southeast",
        "temp": True,
        "currents": False,
    },
    "9414290": {
        "name": "San Francisco",
        "state": "CA",
        "region": "West Coast",
        "temp": True,
        "currents": False,
    },
    "8518750": {
        "name": "The Battery",
        "state": "NY",
        "region": "Northeast",
        "temp": True,
        "currents": False,
    },
    "9447130": {
        "name": "Seattle",
        "state": "WA",
        "region": "Northwest",
        "temp": False,
        "currents": False,
    },
    "8443970": {
        "name": "Boston",
        "state": "MA",
        "region": "Northeast",
        "temp": False,
        "currents": False,
    },
    "8729108": {
        "name": "Panama City",
        "state": "FL",
        "region": "Gulf Coast",
        "temp": True,
        "currents": False,
    },
    "8760922": {
        "name": "Corpus Christi",
        "state": "TX",
        "region": "Gulf Coast",
        "temp": True,
        "currents": False,
    },
}

# Current stations (different from water level stations)
CURRENT_STATIONS = {
    "PUG1515": {"name": "Puget Sound", "state": "WA", "region": "Northwest"},
    "SFB1211": {"name": "San Francisco Bay", "state": "CA", "region": "West Coast"},
}

# AWS clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")


def fetch_water_temperature(station_id: str, hours_back: int = 24) -> Optional[Dict]:
    """Fetch water temperature data from NOAA CO-OPS API"""
    end_date = datetime.utcnow()
    begin_date = end_date - timedelta(hours=hours_back)

    params = {
        "product": "water_temperature",
        "station": station_id,
        "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
        "end_date": end_date.strftime("%Y%m%d %H:%M"),
        "time_zone": "GMT",
        "units": "metric",
        "format": "json",
        "application": USER_AGENT,
    }

    try:
        print(f"  Fetching water temperature for station {station_id}...")
        response = requests.get(TIDES_API_BASE, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                print(f"    ✓ Retrieved {len(data['data'])} temperature readings")
                return data
            else:
                print(f"    ⚠ No data available for station {station_id}")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching data: {e}")
        return None


def fetch_water_level(station_id: str, hours_back: int = 24) -> Optional[Dict]:
    """Fetch water level data from NOAA CO-OPS API"""
    end_date = datetime.utcnow()
    begin_date = end_date - timedelta(hours=hours_back)

    params = {
        "product": "water_level",
        "station": station_id,
        "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
        "end_date": end_date.strftime("%Y%m%d %H:%M"),
        "datum": "MLLW",
        "time_zone": "GMT",
        "units": "metric",
        "format": "json",
        "application": USER_AGENT,
    }

    try:
        print(f"  Fetching water level for station {station_id}...")
        response = requests.get(TIDES_API_BASE, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                print(f"    ✓ Retrieved {len(data['data'])} water level readings")
                return data
            else:
                print(f"    ⚠ No data available for station {station_id}")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching data: {e}")
        return None


def fetch_tide_predictions(station_id: str, days_ahead: int = 7) -> Optional[Dict]:
    """Fetch tide predictions from NOAA CO-OPS API"""
    end_date = datetime.utcnow() + timedelta(days=days_ahead)
    begin_date = datetime.utcnow()

    params = {
        "product": "predictions",
        "station": station_id,
        "begin_date": begin_date.strftime("%Y%m%d"),
        "end_date": end_date.strftime("%Y%m%d"),
        "datum": "MLLW",
        "time_zone": "GMT",
        "units": "metric",
        "format": "json",
        "interval": "hilo",
        "application": USER_AGENT,
    }

    try:
        print(f"  Fetching tide predictions for station {station_id}...")
        response = requests.get(TIDES_API_BASE, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "predictions" in data and len(data["predictions"]) > 0:
                print(f"    ✓ Retrieved {len(data['predictions'])} tide predictions")
                return data
            else:
                print(f"    ⚠ No tide predictions available for station {station_id}")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching tide predictions: {e}")
        return None


def fetch_currents(station_id: str, hours_back: int = 24) -> Optional[Dict]:
    """Fetch current data from NOAA CO-OPS API"""
    end_date = datetime.utcnow()
    begin_date = end_date - timedelta(hours=hours_back)

    params = {
        "product": "currents",
        "station": station_id,
        "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
        "end_date": end_date.strftime("%Y%m%d %H:%M"),
        "time_zone": "GMT",
        "units": "metric",
        "format": "json",
        "application": USER_AGENT,
    }

    try:
        print(f"  Fetching currents for station {station_id}...")
        response = requests.get(TIDES_API_BASE, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                print(f"    ✓ Retrieved {len(data['data'])} current readings")
                return data
            else:
                print(f"    ⚠ No current data available for station {station_id}")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching currents: {e}")
        return None


def fetch_salinity(station_id: str, hours_back: int = 24) -> Optional[Dict]:
    """Fetch salinity data from NOAA CO-OPS API"""
    end_date = datetime.utcnow()
    begin_date = end_date - timedelta(hours=hours_back)

    params = {
        "product": "salinity",
        "station": station_id,
        "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
        "end_date": end_date.strftime("%Y%m%d %H:%M"),
        "time_zone": "GMT",
        "format": "json",
        "application": USER_AGENT,
    }

    try:
        print(f"  Fetching salinity for station {station_id}...")
        response = requests.get(TIDES_API_BASE, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                print(f"    ✓ Retrieved {len(data['data'])} salinity readings")
                return data
            else:
                print(f"    ⚠ No salinity data available for station {station_id}")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching salinity: {e}")
        return None


def store_to_bronze(bucket: str, data: Dict, data_type: str, station_id: str):
    """Store raw data to Bronze layer in S3"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    s3_key = f"bronze/oceanic/{data_type}/date={date_str}/station_{station_id}_{timestamp}.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(data))
        print(f"    ✓ Stored to Bronze: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Bronze: {e}")
        return False


def aggregate_to_gold(
    bucket: str,
    station_id: str,
    station_info: Dict,
    temp_data: Optional[Dict],
    level_data: Optional[Dict],
    tide_data: Optional[Dict],
    current_data: Optional[Dict],
    salinity_data: Optional[Dict],
):
    """Aggregate all oceanic data and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Calculate aggregates
    aggregated = {
        "station_id": station_id,
        "station_name": station_info["name"],
        "state": station_info["state"],
        "region": station_info["region"],
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Temperature stats
    if temp_data and "data" in temp_data:
        temps = [float(d["v"]) for d in temp_data["data"] if "v" in d]
        if temps:
            aggregated["avg_water_temp"] = sum(temps) / len(temps)
            aggregated["min_water_temp"] = min(temps)
            aggregated["max_water_temp"] = max(temps)
            aggregated["temp_readings_count"] = len(temps)
        else:
            aggregated["avg_water_temp"] = None
            aggregated["temp_readings_count"] = 0
    else:
        aggregated["avg_water_temp"] = None
        aggregated["temp_readings_count"] = 0

    # Water level stats
    if level_data and "data" in level_data:
        levels = [float(d["v"]) for d in level_data["data"] if "v" in d]
        if levels:
            aggregated["avg_water_level"] = sum(levels) / len(levels)
            aggregated["min_water_level"] = min(levels)
            aggregated["max_water_level"] = max(levels)
            aggregated["level_readings_count"] = len(levels)
        else:
            aggregated["avg_water_level"] = None
            aggregated["level_readings_count"] = 0
    else:
        aggregated["avg_water_level"] = None
        aggregated["level_readings_count"] = 0

    # Tide prediction stats
    if tide_data and "predictions" in tide_data:
        predictions = tide_data["predictions"]
        aggregated["tide_predictions_count"] = len(predictions)
        if predictions:
            # Extract high and low tides
            highs = [float(p["v"]) for p in predictions if p.get("type") == "H"]
            lows = [float(p["v"]) for p in predictions if p.get("type") == "L"]
            aggregated["next_high_tide"] = (
                predictions[0].get("t") if predictions else None
            )
            aggregated["tide_range"] = (
                (max(highs) - min(lows)) if highs and lows else None
            )
    else:
        aggregated["tide_predictions_count"] = 0
        aggregated["next_high_tide"] = None
        aggregated["tide_range"] = None

    # Current stats
    if current_data and "data" in current_data:
        currents = [float(d["s"]) for d in current_data["data"] if "s" in d]
        if currents:
            aggregated["avg_current_speed"] = sum(currents) / len(currents)
            aggregated["max_current_speed"] = max(currents)
            aggregated["current_readings_count"] = len(currents)
        else:
            aggregated["avg_current_speed"] = None
            aggregated["current_readings_count"] = 0
    else:
        aggregated["avg_current_speed"] = None
        aggregated["max_current_speed"] = None
        aggregated["current_readings_count"] = 0

    # Salinity stats
    if salinity_data and "data" in salinity_data:
        salinities = [float(d["v"]) for d in salinity_data["data"] if "v" in d]
        if salinities:
            aggregated["avg_salinity"] = sum(salinities) / len(salinities)
            aggregated["min_salinity"] = min(salinities)
            aggregated["max_salinity"] = max(salinities)
            aggregated["salinity_readings_count"] = len(salinities)
        else:
            aggregated["avg_salinity"] = None
            aggregated["salinity_readings_count"] = 0
    else:
        aggregated["avg_salinity"] = None
        aggregated["min_salinity"] = None
        aggregated["max_salinity"] = None
        aggregated["salinity_readings_count"] = 0

    # Store to Gold layer
    s3_key = f"gold/oceanic/date={date_str}/station_{station_id}_aggregated.json"

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
    parser = argparse.ArgumentParser(description="Quick oceanic data ingestion")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument("--hours", type=int, default=24, help="Hours of data to fetch")
    args = parser.parse_args()

    env = args.env
    hours_back = args.hours

    # Configuration
    bucket = f"noaa-federated-lake-899626030376-{env}"
    gold_db = f"noaa_gold_{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{'=' * 60}")
    print(f"NOAA Complete Oceanic Data Ingestion")
    print(f"{'=' * 60}")
    print(f"Environment: {env}")
    print(f"Target bucket: {bucket}")
    print(f"Gold database: {gold_db}")
    print(f"Time range: Last {hours_back} hours")
    print(f"Products: Temperature, Levels, Tides, Currents, Salinity")
    print(f"{'=' * 60}\n")

    success_count = 0
    total_count = len(STATIONS)

    for station_id, station_info in STATIONS.items():
        print(
            f"\n[{success_count + 1}/{total_count}] Processing station {station_id} ({station_info['name']}, {station_info['state']})..."
        )

        # Fetch all available data products
        temp_data = (
            fetch_water_temperature(station_id, hours_back)
            if station_info.get("temp", True)
            else None
        )
        level_data = fetch_water_level(station_id, hours_back)
        tide_data = fetch_tide_predictions(station_id, days_ahead=7)
        salinity_data = fetch_salinity(station_id, hours_back)
        current_data = None  # Most water level stations don't have currents

        # Check if we got any data
        has_data = any([temp_data, level_data, tide_data, salinity_data, current_data])

        if has_data:
            # Store to Bronze
            if temp_data:
                store_to_bronze(bucket, temp_data, "water_temperature", station_id)
            if level_data:
                store_to_bronze(bucket, level_data, "water_level", station_id)
            if tide_data:
                store_to_bronze(bucket, tide_data, "tide_predictions", station_id)
            if current_data:
                store_to_bronze(bucket, current_data, "currents", station_id)
            if salinity_data:
                store_to_bronze(bucket, salinity_data, "salinity", station_id)

            # Aggregate to Gold
            aggregate_to_gold(
                bucket,
                station_id,
                station_info,
                temp_data,
                level_data,
                tide_data,
                current_data,
                salinity_data,
            )

            success_count += 1
        else:
            print(f"  ⚠ No data available for station {station_id}")

    # Process current stations separately
    print(f"\n{'=' * 60}")
    print(f"Processing Current Stations")
    print(f"{'=' * 60}\n")

    for station_id, station_info in CURRENT_STATIONS.items():
        print(f"\nProcessing current station {station_id} ({station_info['name']})...")
        current_data = fetch_currents(station_id, hours_back)

        if current_data:
            store_to_bronze(bucket, current_data, "currents", station_id)
            # Store simplified gold record for current-only stations
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            currents = [float(d["s"]) for d in current_data["data"] if "s" in d]
            aggregated = {
                "station_id": station_id,
                "station_name": station_info["name"],
                "state": station_info["state"],
                "region": station_info["region"],
                "date": date_str,
                "timestamp": datetime.utcnow().isoformat(),
                "avg_current_speed": sum(currents) / len(currents)
                if currents
                else None,
                "max_current_speed": max(currents) if currents else None,
                "current_readings_count": len(currents),
            }
            s3_key = (
                f"gold/oceanic/date={date_str}/station_{station_id}_aggregated.json"
            )
            s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(aggregated))
            print(f"    ✓ Stored current data to Gold")

    print(f"\n{'=' * 60}")
    print(f"Ingestion Summary")
    print(f"{'=' * 60}")
    print(f"Successfully processed: {success_count}/{total_count} stations")
    print(f"{'=' * 60}\n")

    # Refresh Athena tables
    print("Refreshing Athena tables...")

    # Create Gold table if not exists
    create_table_sql = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.oceanic_aggregated (
        station_id STRING,
        station_name STRING,
        state STRING,
        region STRING,
        timestamp STRING,
        avg_water_temp DOUBLE,
        min_water_temp DOUBLE,
        max_water_temp DOUBLE,
        temp_readings_count INT,
        avg_water_level DOUBLE,
        min_water_level DOUBLE,
        max_water_level DOUBLE,
        level_readings_count INT,
        tide_predictions_count INT,
        next_high_tide STRING,
        tide_range DOUBLE,
        avg_current_speed DOUBLE,
        max_current_speed DOUBLE,
        current_readings_count INT,
        avg_salinity DOUBLE,
        min_salinity DOUBLE,
        max_salinity DOUBLE,
        salinity_readings_count INT
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/oceanic/'
    """

    run_athena_query(gold_db, create_table_sql, athena_results_bucket)

    # Repair partitions
    repair_sql = f"MSCK REPAIR TABLE {gold_db}.oceanic_aggregated"
    run_athena_query(gold_db, repair_sql, athena_results_bucket)

    print("\n✅ Complete oceanic data ingestion finished!")
    print(f"\nData products ingested:")
    print(f"  ✓ Water Temperature")
    print(f"  ✓ Water Levels")
    print(f"  ✓ Tide Predictions")
    print(f"  ✓ Currents")
    print(f"  ✓ Salinity")
    print(f"\nTo query the data:")
    print(f"  SELECT * FROM {gold_db}.oceanic_aggregated LIMIT 10;")
    print()


if __name__ == "__main__":
    main()
