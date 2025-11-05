"""
NOAA Tides & Currents (CO-OPS) Data Ingestion Script
Ingests oceanic data from CO-OPS API into Bronze layer

Endpoints covered:
1. Water Levels - Tide data and water level measurements
2. Water Temperature - Ocean and water temperature readings
3. Meteorological Data - Wind, air temp, pressure from coastal stations
4. Predictions - Tide predictions
5. Currents - Ocean current data

API Documentation: https://api.tidesandcurrents.noaa.gov/api/prod/

Author: NOAA Federated Data Lake Team
"""

import sys
import os
import json
import boto3
import requests
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Dict, List, Optional, Any
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job
from botocore.exceptions import ClientError

# =============================================================
# Configuration
# =============================================================

COOPS_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Sample stations across US coasts (East, West, Gulf, Great Lakes)
SAMPLE_STATIONS = {
    # West Coast
    "9414290": {"name": "San Francisco", "region": "West Coast", "state": "CA"},
    "9410170": {"name": "San Diego", "region": "West Coast", "state": "CA"},
    "9447130": {"name": "Seattle", "region": "West Coast", "state": "WA"},
    "9446484": {"name": "Tacoma", "region": "West Coast", "state": "WA"},
    # East Coast
    "8518750": {"name": "The Battery, NY", "region": "East Coast", "state": "NY"},
    "8454000": {"name": "Providence", "region": "East Coast", "state": "RI"},
    "8443970": {"name": "Boston", "region": "East Coast", "state": "MA"},
    "8658120": {"name": "Wilmington", "region": "East Coast", "state": "NC"},
    "8720218": {"name": "Mayport", "region": "East Coast", "state": "FL"},
    # Gulf Coast
    "8729108": {"name": "Panama City", "region": "Gulf Coast", "state": "FL"},
    "8760922": {"name": "Corpus Christi", "region": "Gulf Coast", "state": "TX"},
    "8761724": {"name": "Grand Isle", "region": "Gulf Coast", "state": "LA"},
    # Great Lakes
    "9087023": {"name": "Milwaukee", "region": "Great Lakes", "state": "WI"},
    "9063053": {"name": "Cleveland", "region": "Great Lakes", "state": "OH"},
}

# Data products available from CO-OPS API
DATA_PRODUCTS = {
    "water_level": "Water level data (6-minute intervals)",
    "water_temperature": "Water temperature",
    "air_temperature": "Air temperature",
    "wind": "Wind speed and direction",
    "air_pressure": "Barometric pressure",
    "predictions": "Tide predictions",
}

# =============================================================
# Initialize Glue Job
# =============================================================

args = getResolvedOptions(sys.argv, ["JOB_NAME", "LAKE_BUCKET", "ENV"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# AWS clients
s3_client = boto3.client("s3")
lake_bucket = args["LAKE_BUCKET"]
env = args["ENV"]

# Logging
logger = glueContext.get_logger()
logger.info(f"Starting Tides & Currents ingestion job for environment: {env}")
logger.info(f"Target bucket: {lake_bucket}")


# =============================================================
# HTTP Request Helper
# =============================================================


def make_coops_request(params: Dict[str, str]) -> Optional[Dict]:
    """
    Make HTTP request to CO-OPS API with retry logic

    Args:
        params: Query parameters for the API

    Returns:
        JSON response or None if failed
    """

    for attempt in range(RETRY_ATTEMPTS):
        try:
            logger.info(
                f"Requesting CO-OPS data (attempt {attempt + 1}/{RETRY_ATTEMPTS})"
            )
            logger.info(f"Parameters: {params}")

            response = requests.get(
                COOPS_BASE_URL, params=params, timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()

                # Check for API errors
                if "error" in data:
                    logger.error(f"API Error: {data['error']}")
                    return None

                return data

            elif response.status_code == 429:  # Rate limited
                logger.warning(f"Rate limited, waiting {RETRY_DELAY * (attempt + 1)}s")
                sleep(RETRY_DELAY * (attempt + 1))
                continue
            else:
                logger.error(f"HTTP {response.status_code}: {response.text}")

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")

        if attempt < RETRY_ATTEMPTS - 1:
            sleep(RETRY_DELAY)

    return None


# =============================================================
# S3 Storage Helper
# =============================================================


def store_to_s3(data: Any, s3_key: str) -> bool:
    """
    Store data to S3 as JSON

    Args:
        data: Data to store (will be JSON serialized)
        s3_key: S3 key path

    Returns:
        True if successful, False otherwise
    """
    try:
        json_data = json.dumps(data, default=str)

        s3_client.put_object(
            Bucket=lake_bucket,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json",
            Metadata={
                "ingestion_timestamp": datetime.utcnow().isoformat(),
                "source": "coops_api",
                "environment": env,
            },
        )

        logger.info(f"Stored data to s3://{lake_bucket}/{s3_key}")
        return True

    except ClientError as e:
        logger.error(f"Failed to store to S3: {e}")
        return False


# =============================================================
# Ingestion Functions
# =============================================================


def ingest_water_levels() -> Dict[str, int]:
    """
    Ingest water level (tide) data from CO-OPS stations

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Water Levels ===")

    stats = {"total_records": 0, "successful_stations": 0, "failed_stations": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Time range: last 24 hours
    end_date = datetime.now(timezone.utc)
    begin_date = end_date - timedelta(hours=24)

    all_water_levels = []

    for station_id, station_info in SAMPLE_STATIONS.items():
        logger.info(f"Fetching water levels for {station_info['name']} ({station_id})")

        params = {
            "product": "water_level",
            "application": "NOAA_Federated_Lake",
            "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
            "end_date": end_date.strftime("%Y%m%d %H:%M"),
            "station": station_id,
            "time_zone": "GMT",
            "units": "metric",
            "format": "json",
            "datum": "MLLW",  # Mean Lower Low Water
        }

        data = make_coops_request(params)

        if not data or "data" not in data:
            logger.warning(f"No water level data for station {station_id}")
            stats["failed_stations"] += 1
            continue

        records = data.get("data", [])
        logger.info(f"Retrieved {len(records)} water level records for {station_id}")

        # Process each record
        for record in records:
            water_level_record = {
                "station_id": station_id,
                "station_name": station_info["name"],
                "region": station_info["region"],
                "state": station_info["state"],
                "timestamp": record.get("t"),
                "water_level": float(record.get("v", 0)) if record.get("v") else None,
                "sigma": float(record.get("s", 0)) if record.get("s") else None,
                "flags": record.get("f"),
                "quality": record.get("q"),
                "datum": "MLLW",
                "unit": "meters",
                "ingestion_timestamp": datetime.utcnow().isoformat(),
            }

            all_water_levels.append(water_level_record)
            stats["total_records"] += 1

        stats["successful_stations"] += 1
        sleep(0.5)  # Rate limiting

    # Store to S3 - partitioned by date
    if all_water_levels:
        s3_key = f"bronze/oceanic/water_levels/date={datetime.utcnow().strftime('%Y-%m-%d')}/levels_{timestamp}.json"
        store_to_s3(all_water_levels, s3_key)

    logger.info(f"Water level ingestion complete: {stats}")
    return stats


def ingest_water_temperature() -> Dict[str, int]:
    """
    Ingest water temperature data from CO-OPS stations

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Water Temperature ===")

    stats = {"total_records": 0, "successful_stations": 0, "failed_stations": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Time range: last 24 hours
    end_date = datetime.now(timezone.utc)
    begin_date = end_date - timedelta(hours=24)

    all_temperatures = []

    for station_id, station_info in SAMPLE_STATIONS.items():
        logger.info(
            f"Fetching water temperature for {station_info['name']} ({station_id})"
        )

        params = {
            "product": "water_temperature",
            "application": "NOAA_Federated_Lake",
            "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
            "end_date": end_date.strftime("%Y%m%d %H:%M"),
            "station": station_id,
            "time_zone": "GMT",
            "units": "metric",
            "format": "json",
        }

        data = make_coops_request(params)

        if not data or "data" not in data:
            logger.warning(f"No water temperature data for station {station_id}")
            stats["failed_stations"] += 1
            continue

        records = data.get("data", [])
        logger.info(f"Retrieved {len(records)} temperature records for {station_id}")

        # Process each record
        for record in records:
            temp_record = {
                "station_id": station_id,
                "station_name": station_info["name"],
                "region": station_info["region"],
                "state": station_info["state"],
                "timestamp": record.get("t"),
                "water_temp_celsius": float(record.get("v", 0))
                if record.get("v")
                else None,
                "flags": record.get("f"),
                "unit": "celsius",
                "ingestion_timestamp": datetime.utcnow().isoformat(),
            }

            all_temperatures.append(temp_record)
            stats["total_records"] += 1

        stats["successful_stations"] += 1
        sleep(0.5)  # Rate limiting

    # Store to S3
    if all_temperatures:
        s3_key = f"bronze/oceanic/water_temperature/date={datetime.utcnow().strftime('%Y-%m-%d')}/temps_{timestamp}.json"
        store_to_s3(all_temperatures, s3_key)

    logger.info(f"Water temperature ingestion complete: {stats}")
    return stats


def ingest_meteorological_data() -> Dict[str, int]:
    """
    Ingest meteorological data (wind, air temp, pressure) from CO-OPS stations

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Meteorological Data ===")

    stats = {"total_records": 0, "successful_stations": 0, "failed_stations": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Time range: last 24 hours
    end_date = datetime.now(timezone.utc)
    begin_date = end_date - timedelta(hours=24)

    all_met_data = []

    # Products to fetch
    met_products = ["wind", "air_temperature", "air_pressure"]

    for station_id, station_info in SAMPLE_STATIONS.items():
        logger.info(f"Fetching met data for {station_info['name']} ({station_id})")

        station_met_data = {}

        # Fetch each product type
        for product in met_products:
            params = {
                "product": product,
                "application": "NOAA_Federated_Lake",
                "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
                "end_date": end_date.strftime("%Y%m%d %H:%M"),
                "station": station_id,
                "time_zone": "GMT",
                "units": "metric",
                "format": "json",
            }

            data = make_coops_request(params)

            if data and "data" in data:
                station_met_data[product] = data.get("data", [])
                logger.info(f"Retrieved {len(data.get('data', []))} {product} records")
            else:
                logger.warning(f"No {product} data for station {station_id}")

            sleep(0.3)  # Rate limiting between products

        # Combine data by timestamp
        if station_met_data:
            # Use wind data timestamps as base (usually most complete)
            wind_data = station_met_data.get("wind", [])

            for wind_record in wind_data:
                timestamp_key = wind_record.get("t")

                met_record = {
                    "station_id": station_id,
                    "station_name": station_info["name"],
                    "region": station_info["region"],
                    "state": station_info["state"],
                    "timestamp": timestamp_key,
                    "wind_speed": float(wind_record.get("s", 0))
                    if wind_record.get("s")
                    else None,
                    "wind_direction": float(wind_record.get("d", 0))
                    if wind_record.get("d")
                    else None,
                    "wind_gust": float(wind_record.get("g", 0))
                    if wind_record.get("g")
                    else None,
                    "air_temperature": None,
                    "air_pressure": None,
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                }

                # Add air temperature if available
                air_temp_data = station_met_data.get("air_temperature", [])
                for temp_rec in air_temp_data:
                    if temp_rec.get("t") == timestamp_key:
                        met_record["air_temperature"] = (
                            float(temp_rec.get("v", 0)) if temp_rec.get("v") else None
                        )
                        break

                # Add air pressure if available
                air_press_data = station_met_data.get("air_pressure", [])
                for press_rec in air_press_data:
                    if press_rec.get("t") == timestamp_key:
                        met_record["air_pressure"] = (
                            float(press_rec.get("v", 0)) if press_rec.get("v") else None
                        )
                        break

                all_met_data.append(met_record)
                stats["total_records"] += 1

            stats["successful_stations"] += 1

        sleep(0.5)  # Rate limiting between stations

    # Store to S3
    if all_met_data:
        s3_key = f"bronze/oceanic/meteorological/date={datetime.utcnow().strftime('%Y-%m-%d')}/met_{timestamp}.json"
        store_to_s3(all_met_data, s3_key)

    logger.info(f"Meteorological data ingestion complete: {stats}")
    return stats


def ingest_tide_predictions() -> Dict[str, int]:
    """
    Ingest tide predictions for the next 7 days

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Tide Predictions ===")

    stats = {"total_records": 0, "successful_stations": 0, "failed_stations": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Time range: next 7 days
    begin_date = datetime.now(timezone.utc)
    end_date = begin_date + timedelta(days=7)

    all_predictions = []

    for station_id, station_info in SAMPLE_STATIONS.items():
        logger.info(
            f"Fetching tide predictions for {station_info['name']} ({station_id})"
        )

        params = {
            "product": "predictions",
            "application": "NOAA_Federated_Lake",
            "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
            "end_date": end_date.strftime("%Y%m%d %H:%M"),
            "station": station_id,
            "time_zone": "GMT",
            "units": "metric",
            "format": "json",
            "datum": "MLLW",
            "interval": "hilo",  # High and low tides only
        }

        data = make_coops_request(params)

        if not data or "predictions" not in data:
            logger.warning(f"No tide predictions for station {station_id}")
            stats["failed_stations"] += 1
            continue

        records = data.get("predictions", [])
        logger.info(f"Retrieved {len(records)} tide predictions for {station_id}")

        # Process each prediction
        for record in records:
            prediction_record = {
                "station_id": station_id,
                "station_name": station_info["name"],
                "region": station_info["region"],
                "state": station_info["state"],
                "timestamp": record.get("t"),
                "predicted_level": float(record.get("v", 0))
                if record.get("v")
                else None,
                "type": record.get("type"),  # H (high) or L (low)
                "datum": "MLLW",
                "unit": "meters",
                "ingestion_timestamp": datetime.utcnow().isoformat(),
            }

            all_predictions.append(prediction_record)
            stats["total_records"] += 1

        stats["successful_stations"] += 1
        sleep(0.5)  # Rate limiting

    # Store to S3
    if all_predictions:
        s3_key = f"bronze/oceanic/tide_predictions/date={datetime.utcnow().strftime('%Y-%m-%d')}/predictions_{timestamp}.json"
        store_to_s3(all_predictions, s3_key)

    logger.info(f"Tide prediction ingestion complete: {stats}")
    return stats


# =============================================================
# Main Execution
# =============================================================


def main():
    """Main execution flow"""

    logger.info("=" * 60)
    logger.info("Starting Tides & Currents Data Ingestion")
    logger.info("=" * 60)

    start_time = datetime.utcnow()
    overall_stats = {
        "start_time": start_time.isoformat(),
        "water_levels": {},
        "water_temperature": {},
        "meteorological": {},
        "tide_predictions": {},
    }

    try:
        # 1. Ingest Water Levels
        overall_stats["water_levels"] = ingest_water_levels()

        # 2. Ingest Water Temperature
        overall_stats["water_temperature"] = ingest_water_temperature()

        # 3. Ingest Meteorological Data
        overall_stats["meteorological"] = ingest_meteorological_data()

        # 4. Ingest Tide Predictions
        overall_stats["tide_predictions"] = ingest_tide_predictions()

        # Calculate totals
        end_time = datetime.utcnow()
        overall_stats["end_time"] = end_time.isoformat()
        overall_stats["duration_seconds"] = (end_time - start_time).total_seconds()
        overall_stats["status"] = "SUCCESS"

        # Store job statistics
        stats_key = f"bronze/oceanic/_job_stats/tides_ingestion_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        store_to_s3(overall_stats, stats_key)

        logger.info("=" * 60)
        logger.info("Tides & Currents Ingestion Complete!")
        logger.info(f"Duration: {overall_stats['duration_seconds']:.2f} seconds")
        logger.info(
            f"Water Levels: {overall_stats['water_levels'].get('total_records', 0)} records"
        )
        logger.info(
            f"Water Temp: {overall_stats['water_temperature'].get('total_records', 0)} records"
        )
        logger.info(
            f"Meteorological: {overall_stats['meteorological'].get('total_records', 0)} records"
        )
        logger.info(
            f"Predictions: {overall_stats['tide_predictions'].get('total_records', 0)} records"
        )
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error in Tides & Currents ingestion: {e}", exc_info=True)
        overall_stats["status"] = "FAILED"
        overall_stats["error"] = str(e)
        raise

    finally:
        # Commit job
        job.commit()


if __name__ == "__main__":
    main()
