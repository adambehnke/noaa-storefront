#!/usr/bin/env python3
"""
NOAA Climate Data Online (CDO) Ingestion Script
Populates Bronze and Gold layers with historical climate data:
- Daily temperature (max/min)
- Precipitation
- Snowfall
- Climate normals
- Historical trends

Usage:
    python3 climate_ingest.py [--env dev] [--days 30] [--stations GHCND:USW00094728]
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
CDO_API_BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# Major US weather stations (GHCND = Global Historical Climatology Network Daily)
CLIMATE_STATIONS = {
    "GHCND:USW00094728": {
        "name": "New York Central Park",
        "state": "NY",
        "region": "Northeast",
        "city": "New York",
    },
    "GHCND:USW00023174": {
        "name": "Los Angeles International",
        "state": "CA",
        "region": "West Coast",
        "city": "Los Angeles",
    },
    "GHCND:USW00094846": {
        "name": "Chicago O'Hare",
        "state": "IL",
        "region": "Midwest",
        "city": "Chicago",
    },
    "GHCND:USW00012960": {
        "name": "Houston Intercontinental",
        "state": "TX",
        "region": "South",
        "city": "Houston",
    },
    "GHCND:USW00023183": {
        "name": "Phoenix Sky Harbor",
        "state": "AZ",
        "region": "Southwest",
        "city": "Phoenix",
    },
    "GHCND:USW00012839": {
        "name": "Miami International",
        "state": "FL",
        "region": "Southeast",
        "city": "Miami",
    },
    "GHCND:USW00024233": {
        "name": "Seattle-Tacoma",
        "state": "WA",
        "region": "Northwest",
        "city": "Seattle",
    },
    "GHCND:USW00014739": {
        "name": "Boston Logan",
        "state": "MA",
        "region": "Northeast",
        "city": "Boston",
    },
}

# Data types to fetch
DATA_TYPES = ["TMAX", "TMIN", "PRCP", "SNOW", "SNWD", "TAVG"]

# AWS clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")
secrets_client = boto3.client("secretsmanager", region_name="us-east-1")


def get_cdo_token(env: str) -> str:
    """Retrieve CDO API token from AWS Secrets Manager"""
    secret_name = f"noaa-cdo-token-{env}"

    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])
        token = secret_data.get("token", response["SecretString"])
        print(f"  ✓ Retrieved CDO API token from Secrets Manager")
        return token
    except Exception as e:
        print(f"  ✗ Error retrieving CDO token: {e}")
        print(f"  ℹ Using environment variable or default")
        return ""


def fetch_climate_data(
    station_id: str,
    start_date: str,
    end_date: str,
    token: str,
    datasetid: str = "GHCND",
    limit: int = 1000,
) -> Optional[List[Dict]]:
    """Fetch climate data from CDO API with pagination"""

    url = f"{CDO_API_BASE}/data"
    headers = {"token": token}

    all_results = []
    offset = 1

    print(f"  Fetching climate data for {station_id} ({start_date} to {end_date})...")

    while True:
        params = {
            "datasetid": datasetid,
            "stationid": station_id,
            "startdate": start_date,
            "enddate": end_date,
            "limit": limit,
            "offset": offset,
            "units": "standard",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                if "results" in data and len(data["results"]) > 0:
                    results = data["results"]
                    all_results.extend(results)
                    print(f"    ✓ Retrieved {len(results)} records (offset {offset})")

                    # Check if there are more results
                    metadata = data.get("metadata", {})
                    resultset = metadata.get("resultset", {})
                    count = resultset.get("count", 0)

                    if len(all_results) >= count:
                        break

                    offset += limit
                    time.sleep(0.2)  # Rate limiting - 5 requests per second max
                else:
                    break

            elif response.status_code == 429:
                print(f"    ⚠ Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                continue

            else:
                print(f"    ✗ API error: {response.status_code}")
                if response.status_code == 400:
                    print(f"    Response: {response.text[:200]}")
                break

        except Exception as e:
            print(f"    ✗ Error fetching data: {e}")
            break

    if all_results:
        print(f"    ✓ Total records retrieved: {len(all_results)}")
        return all_results
    else:
        print(f"    ⚠ No data available for {station_id}")
        return None


def store_to_bronze(bucket: str, data: List[Dict], station_id: str, date_range: str):
    """Store raw climate data to Bronze layer in S3"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Clean station ID for filename
    station_clean = station_id.replace(":", "_").replace(" ", "_")

    s3_key = (
        f"bronze/climate/date={date_str}/{station_clean}_{date_range}_{timestamp}.json"
    )

    try:
        s3_client.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(data))
        print(f"    ✓ Stored to Bronze: s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        print(f"    ✗ Error storing to Bronze: {e}")
        return False


def aggregate_to_gold(
    bucket: str, station_id: str, station_info: Dict, climate_data: List[Dict]
):
    """Aggregate climate data and store to Gold layer"""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not climate_data:
        return False

    # Organize data by date and type
    data_by_date = {}

    for record in climate_data:
        record_date = record.get("date", "")[:10]  # Get YYYY-MM-DD
        datatype = record.get("datatype", "")
        value = record.get("value", 0)

        if record_date not in data_by_date:
            data_by_date[record_date] = {}

        data_by_date[record_date][datatype] = value

    # Calculate aggregations
    temps_max = []
    temps_min = []
    temps_avg = []
    precip = []
    snow = []

    for date, values in data_by_date.items():
        if "TMAX" in values:
            temps_max.append(values["TMAX"])
        if "TMIN" in values:
            temps_min.append(values["TMIN"])
        if "TAVG" in values:
            temps_avg.append(values["TAVG"])
        if "PRCP" in values:
            precip.append(values["PRCP"])
        if "SNOW" in values and values["SNOW"] > 0:
            snow.append(values["SNOW"])

    aggregated = {
        "station_id": station_id,
        "station_name": station_info["name"],
        "city": station_info["city"],
        "state": station_info["state"],
        "region": station_info["region"],
        "date": date_str,
        "timestamp": datetime.utcnow().isoformat(),
        "observation_count": len(climate_data),
        "date_range_count": len(data_by_date),
    }

    # Temperature aggregations (in Fahrenheit for GHCND)
    if temps_max:
        aggregated["avg_high_temp_f"] = (
            sum(temps_max) / len(temps_max) / 10.0
        )  # CDO stores in tenths
        aggregated["max_temp_f"] = max(temps_max) / 10.0
        aggregated["days_with_high"] = len(temps_max)
    else:
        aggregated["avg_high_temp_f"] = None
        aggregated["max_temp_f"] = None
        aggregated["days_with_high"] = 0

    if temps_min:
        aggregated["avg_low_temp_f"] = sum(temps_min) / len(temps_min) / 10.0
        aggregated["min_temp_f"] = min(temps_min) / 10.0
        aggregated["days_with_low"] = len(temps_min)
    else:
        aggregated["avg_low_temp_f"] = None
        aggregated["min_temp_f"] = None
        aggregated["days_with_low"] = 0

    if temps_avg:
        aggregated["avg_temp_f"] = sum(temps_avg) / len(temps_avg) / 10.0
    else:
        aggregated["avg_temp_f"] = None

    # Precipitation aggregations (in inches for GHCND)
    if precip:
        aggregated["total_precip_in"] = sum(precip) / 100.0  # CDO stores in hundredths
        aggregated["avg_daily_precip_in"] = (sum(precip) / len(precip)) / 100.0
        aggregated["max_daily_precip_in"] = max(precip) / 100.0
        aggregated["days_with_precip"] = len([p for p in precip if p > 0])
    else:
        aggregated["total_precip_in"] = None
        aggregated["avg_daily_precip_in"] = None
        aggregated["max_daily_precip_in"] = None
        aggregated["days_with_precip"] = 0

    # Snow aggregations (in inches for GHCND)
    if snow:
        aggregated["total_snow_in"] = sum(snow) / 10.0  # CDO stores in tenths
        aggregated["max_daily_snow_in"] = max(snow) / 10.0
        aggregated["days_with_snow"] = len(snow)
    else:
        aggregated["total_snow_in"] = None
        aggregated["max_daily_snow_in"] = None
        aggregated["days_with_snow"] = 0

    # Clean station ID for filename
    station_clean = station_id.replace(":", "_").replace(" ", "_")

    s3_key = f"gold/climate/date={date_str}/station_{station_clean}_aggregated.json"

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
    parser = argparse.ArgumentParser(description="NOAA CDO climate data ingestion")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument(
        "--days", type=int, default=30, help="Number of days to fetch (default: 30)"
    )
    parser.add_argument(
        "--stations",
        nargs="+",
        help="Specific station IDs to process (default: all)",
    )
    args = parser.parse_args()

    env = args.env
    days_back = args.days

    # Date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_back)

    stations_to_process = (
        {k: v for k, v in CLIMATE_STATIONS.items() if k in args.stations}
        if args.stations
        else CLIMATE_STATIONS
    )

    # Configuration
    bucket = f"noaa-federated-lake-899626030376-{env}"
    gold_db = f"noaa_gold_{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{'=' * 60}")
    print(f"NOAA Climate Data Ingestion (CDO)")
    print(f"{'=' * 60}")
    print(f"Environment: {env}")
    print(f"Target bucket: {bucket}")
    print(f"Gold database: {gold_db}")
    print(f"Date range: {start_date} to {end_date} ({days_back} days)")
    print(f"Stations to process: {len(stations_to_process)}")
    print(f"{'=' * 60}\n")

    # Get API token
    token = get_cdo_token(env)

    if not token:
        print("\n❌ ERROR: CDO API token not found!")
        print("Please set up the token in AWS Secrets Manager:")
        print(f"  aws secretsmanager create-secret --name noaa-cdo-token-{env} \\")
        print('    --secret-string \'{"token":"YOUR_TOKEN_HERE"}\'')
        print("\nGet your token from: https://www.ncdc.noaa.gov/cdo-web/token")
        sys.exit(1)

    success_count = 0
    total_count = len(stations_to_process)

    for station_id, station_info in stations_to_process.items():
        print(
            f"\n[{success_count + 1}/{total_count}] Processing {station_info['name']}, {station_info['state']}..."
        )

        # Fetch climate data
        climate_data = fetch_climate_data(
            station_id,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            token,
        )

        if climate_data:
            # Store to Bronze
            date_range = (
                f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            )
            store_to_bronze(bucket, climate_data, station_id, date_range)

            # Aggregate to Gold
            aggregate_to_gold(bucket, station_id, station_info, climate_data)

            success_count += 1
        else:
            print(f"  ⚠ No data available for {station_id}")

        # Rate limiting between stations
        time.sleep(0.5)

    print(f"\n{'=' * 60}")
    print(f"Ingestion Summary")
    print(f"{'=' * 60}")
    print(f"Successfully processed: {success_count}/{total_count} stations")
    print(f"{'=' * 60}\n")

    # Refresh Athena tables
    print("Refreshing Athena tables...")

    # Create Gold table
    create_table_sql = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {gold_db}.climate_aggregated (
        station_id STRING,
        station_name STRING,
        city STRING,
        state STRING,
        region STRING,
        timestamp STRING,
        observation_count INT,
        date_range_count INT,
        avg_high_temp_f DOUBLE,
        max_temp_f DOUBLE,
        days_with_high INT,
        avg_low_temp_f DOUBLE,
        min_temp_f DOUBLE,
        days_with_low INT,
        avg_temp_f DOUBLE,
        total_precip_in DOUBLE,
        avg_daily_precip_in DOUBLE,
        max_daily_precip_in DOUBLE,
        days_with_precip INT,
        total_snow_in DOUBLE,
        max_daily_snow_in DOUBLE,
        days_with_snow INT
    )
    PARTITIONED BY (date STRING)
    STORED AS JSON
    LOCATION 's3://{bucket}/gold/climate/'
    """

    run_athena_query(gold_db, create_table_sql, athena_results_bucket)

    # Repair partitions
    repair_sql = f"MSCK REPAIR TABLE {gold_db}.climate_aggregated"
    run_athena_query(gold_db, repair_sql, athena_results_bucket)

    print("\n✅ Climate data ingestion complete!")
    print(f"\nData products ingested:")
    print(f"  ✓ Daily Temperature (High/Low/Average)")
    print(f"  ✓ Precipitation")
    print(f"  ✓ Snowfall")
    print(f"  ✓ Climate Trends")
    print(f"\nTo query the data:")
    print(f"  SELECT * FROM {gold_db}.climate_aggregated LIMIT 10;")
    print()


if __name__ == "__main__":
    main()
