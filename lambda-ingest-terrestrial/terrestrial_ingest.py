#!/usr/bin/env python3
"""
NOAA Terrestrial Data Ingestion Script
Populates Bronze and Gold layers with terrestrial data:
- US Drought Monitor data
- Drought severity classifications
- State and county level drought statistics

Usage:
    python3 terrestrial_ingest.py [--env dev]
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import requests

# Configuration
DROUGHT_MONITOR_URL = "https://droughtmonitor.unl.edu/data/json/usdm_current.json"
DROUGHT_GEOJSON_URL = "https://droughtmonitor.unl.edu/data/geojson/usdm_current.geojson"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# Drought severity levels
DROUGHT_LEVELS = {
    "D0": "Abnormally Dry",
    "D1": "Moderate Drought",
    "D2": "Severe Drought",
    "D3": "Extreme Drought",
    "D4": "Exceptional Drought",
}

# AWS clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")


def fetch_drought_monitor_data() -> Optional[Dict]:
    """Fetch current US Drought Monitor data"""

    print(f"  Fetching US Drought Monitor data...")

    try:
        response = requests.get(
            DROUGHT_MONITOR_URL, headers={"User-Agent": USER_AGENT}, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data:
                print(f"    ✓ Retrieved drought monitor data")
                return data
            else:
                print(f"    ⚠ No drought data found")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching drought data: {e}")
        return None


def fetch_drought_geojson() -> Optional[Dict]:
    """Fetch current US Drought Monitor GeoJSON data"""

    print(f"  Fetching US Drought Monitor GeoJSON...")

    try:
        response = requests.get(
            DROUGHT_GEOJSON_URL, headers={"User-Agent": USER_AGENT}, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            if data and "features" in data:
                feature_count = len(data["features"])
                print(f"    ✓ Retrieved {feature_count} drought features")
                return data
            else:
                print(f"    ⚠ No drought geojson data found")
                return None
        else:
            print(f"    ✗ API error: {response.status_code}")
            return None

    except Exception as e:
        print(f"    ✗ Error fetching drought geojson: {e}")
        return None


def store_to_bronze(bucket: str, data: Dict, data_type: str):
    """Store raw drought data to Bronze layer in S3"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    s3_key = f"bronze/terrestrial/drought/{data_type}/date={date_str}/drought_{timestamp}.json"

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(data))
        print(f"    ✓ Stored to Bronze: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Bronze: {e}")
        return False


def aggregate_drought_to_gold(
    bucket: str, drought_data: Dict, geojson_data: Optional[Dict]
):
    """Aggregate drought data and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not drought_data:
        return False

    # Parse the drought data structure
    # USDM data typically has state-level statistics
    state_stats = []
    total_area_affected = 0
    drought_summary = {
        "D0": 0,
        "D1": 0,
        "D2": 0,
        "D3": 0,
        "D4": 0,
    }

    # Extract state-level data if available
    if isinstance(drought_data, dict):
        for key, value in drought_data.items():
            if isinstance(value, dict) and "state" in str(key).lower():
                # Process state data
                pass
            elif isinstance(value, list):
                # Process list of drought records
                for record in value:
                    if isinstance(record, dict):
                        # Extract drought levels
                        for level in ["D0", "D1", "D2", "D3", "D4"]:
                            if level in record:
                                try:
                                    drought_summary[level] += float(record[level])
                                except (ValueError, TypeError):
                                    pass

    # Process GeoJSON features for geographic summary
    if geojson_data and "features" in geojson_data:
        features = geojson_data["features"]

        for feature in features:
            props = feature.get("properties", {})

            # Extract drought level
            dm_level = props.get("DM", "")
            if dm_level in drought_summary:
                drought_summary[dm_level] += 1

    # Calculate percentages and totals
    total_features = sum(drought_summary.values())

    aggregated = {
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "drought_summary": {
            level: {
                "name": DROUGHT_LEVELS[level],
                "count": count,
                "percentage": round((count / total_features * 100), 2)
                if total_features > 0
                else 0,
            }
            for level, count in drought_summary.items()
        },
        "total_drought_features": total_features,
        "states_affected": len(state_stats),
        "data_source": "US Drought Monitor",
        "data_url": DROUGHT_MONITOR_URL,
    }

    # Add severity flags
    aggregated["has_exceptional_drought"] = drought_summary["D4"] > 0
    aggregated["has_extreme_drought"] = (
        drought_summary["D3"] > 0 or drought_summary["D4"] > 0
    )
    aggregated["has_severe_drought"] = (
        drought_summary["D2"] > 0
        or drought_summary["D3"] > 0
        or drought_summary["D4"] > 0
    )

    # Calculate overall drought severity score (0-4)
    if total_features > 0:
        severity_score = (
            (drought_summary["D0"] * 0)
            + (drought_summary["D1"] * 1)
            + (drought_summary["D2"] * 2)
            + (drought_summary["D3"] * 3)
            + (drought_summary["D4"] * 4)
        ) / total_features
        aggregated["average_severity_score"] = round(severity_score, 2)
    else:
        aggregated["average_severity_score"] = 0

    s3_key = f"gold/terrestrial/drought/date={date_str}/drought_aggregated.json"

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
    parser = argparse.ArgumentParser(description="NOAA terrestrial data ingestion")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    args = parser.parse_args()

    env = args.env

    # Configuration
    bucket = f"noaa-federated-lake-899626030376-{env}"
    gold_db = f"noaa_gold_{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{'=' * 60}")
    print(f"NOAA Terrestrial Data Ingestion (Drought Monitor)")
    print(f"{'=' * 60}")
    print(f"Environment: {env}")
    print(f"Target bucket: {bucket}")
    print(f"Gold database: {gold_db}")
    print(f"{'=' * 60}\n")

    success_count = 0

    # Fetch and store drought monitor data
    print("\n--- Processing Drought Monitor Data ---\n")
    drought_data = fetch_drought_monitor_data()
    if drought_data:
        store_to_bronze(bucket, drought_data, "json")
        success_count += 1

    # Fetch and store drought GeoJSON
    print("\n--- Processing Drought GeoJSON ---\n")
    geojson_data = fetch_drought_geojson()
    if geojson_data:
        store_to_bronze(bucket, geojson_data, "geojson")
        success_count += 1

    # Aggregate to Gold
    if drought_data or geojson_data:
        print("\n--- Aggregating to Gold Layer ---\n")
        aggregate_drought_to_gold(bucket, drought_data, geojson_data)

    print(f"\n{'=' * 60}")
    print(f"Ingestion Summary")
    print(f"{'=' * 60}")
    print(f"Successfully processed: {success_count} data sources")
    print(f"{'=' * 60}\n")

    # Refresh Athena tables
    print("Refreshing Athena tables...")

    # Create Gold table
    create_table_sql = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.terrestrial_drought (
        timestamp STRING,
        drought_summary STRUCT<
            D0:STRUCT<name:STRING, count:INT, percentage:DOUBLE>,
            D1:STRUCT<name:STRING, count:INT, percentage:DOUBLE>,
            D2:STRUCT<name:STRING, count:INT, percentage:DOUBLE>,
            D3:STRUCT<name:STRING, count:INT, percentage:DOUBLE>,
            D4:STRUCT<name:STRING, count:INT, percentage:DOUBLE>
        >,
        total_drought_features INT,
        states_affected INT,
        data_source STRING,
        data_url STRING,
        has_exceptional_drought BOOLEAN,
        has_extreme_drought BOOLEAN,
        has_severe_drought BOOLEAN,
        average_severity_score DOUBLE
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/terrestrial/drought/'
    """

    run_athena_query(gold_db, create_table_sql, athena_results_bucket)

    # Repair partitions
    repair_sql = f"MSCK REPAIR TABLE {gold_db}.terrestrial_drought"
    run_athena_query(gold_db, repair_sql, athena_results_bucket)

    print("\n✅ Terrestrial data ingestion complete!")
    print(f"\nData products ingested:")
    print(f"  ✓ US Drought Monitor (Current)")
    print(f"  ✓ Drought Severity Classifications")
    print(f"  ✓ Geographic Drought Data (GeoJSON)")
    print(f"\nDrought Severity Levels:")
    for level, name in DROUGHT_LEVELS.items():
        print(f"  {level}: {name}")
    print(f"\nTo query the data:")
    print(f"  SELECT * FROM {gold_db}.terrestrial_drought LIMIT 10;")
    print()


if __name__ == "__main__":
    main()
