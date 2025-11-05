"""
Enhanced NWS (National Weather Service) Data Ingestion Script
Ingests data from multiple NWS API endpoints into Bronze layer

Endpoints covered:
1. Active Alerts - Weather alerts and warnings
2. Weather Observations - Current conditions from stations
3. Forecast Zones - Zone-based forecasts
4. Radar Stations - Radar station metadata

Author: NOAA Federated Data Lake Team
"""

import sys
import os
import json
import boto3
import requests
from datetime import datetime, timezone
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

NWS_BASE_URL = "https://api.weather.gov"
NWS_USER_AGENT = "NOAA-Federated-Data-Lake/1.0 (data-team@example.com)"
REQUEST_TIMEOUT = 15
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Key US states for initial ingestion
PRIORITY_STATES = ["CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI"]

# Sample weather stations across different regions
SAMPLE_STATIONS = [
    "KSFO",  # San Francisco, CA
    "KLAX",  # Los Angeles, CA
    "KJFK",  # New York, NY
    "KORD",  # Chicago, IL
    "KATL",  # Atlanta, GA
    "KDFW",  # Dallas, TX
    "KDEN",  # Denver, CO
    "KSEA",  # Seattle, WA
    "KMIA",  # Miami, FL
    "KBOS",  # Boston, MA
    "KPHX",  # Phoenix, AZ
    "KLAS",  # Las Vegas, NV
]

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
logger.info(f"Starting NWS ingestion job for environment: {env}")
logger.info(f"Target bucket: {lake_bucket}")


# =============================================================
# HTTP Request Helper
# =============================================================


def make_nws_request(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """
    Make HTTP request to NWS API with retry logic

    Args:
        endpoint: API endpoint path (e.g., '/alerts/active')
        params: Query parameters

    Returns:
        JSON response or None if failed
    """
    url = f"{NWS_BASE_URL}{endpoint}"
    headers = {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}

    for attempt in range(RETRY_ATTEMPTS):
        try:
            logger.info(f"Requesting: {url} (attempt {attempt + 1}/{RETRY_ATTEMPTS})")
            response = requests.get(
                url, headers=headers, params=params, timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limited
                logger.warning(f"Rate limited, waiting {RETRY_DELAY * (attempt + 1)}s")
                sleep(RETRY_DELAY * (attempt + 1))
                continue
            elif response.status_code == 404:
                logger.warning(f"Endpoint not found: {url}")
                return None
            else:
                logger.error(f"HTTP {response.status_code}: {response.text}")

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")

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
                "source": "nws_api",
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


def ingest_active_alerts() -> Dict[str, int]:
    """
    Ingest active weather alerts from NWS

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Active Alerts ===")

    stats = {"total": 0, "by_state": {}, "by_severity": {}}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Get all active alerts
    data = make_nws_request("/alerts/active")

    if not data or "features" not in data:
        logger.warning("No alert data retrieved")
        return stats

    features = data.get("features", [])
    stats["total"] = len(features)

    logger.info(f"Retrieved {len(features)} active alerts")

    # Process and enrich alerts
    processed_alerts = []
    for feature in features:
        props = feature.get("properties", {})

        # Extract key information
        alert_record = {
            "id": props.get("id"),
            "event": props.get("event"),
            "severity": props.get("severity"),
            "certainty": props.get("certainty"),
            "urgency": props.get("urgency"),
            "headline": props.get("headline"),
            "description": props.get("description"),
            "instruction": props.get("instruction"),
            "response": props.get("response"),
            "areaDesc": props.get("areaDesc"),
            "onset": props.get("onset"),
            "expires": props.get("expires"),
            "status": props.get("status"),
            "messageType": props.get("messageType"),
            "category": props.get("category"),
            "sender": props.get("sender"),
            "senderName": props.get("senderName"),
            "geometry": feature.get("geometry"),
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        processed_alerts.append(alert_record)

        # Track statistics
        severity = props.get("severity", "Unknown")
        stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

    # Store to S3
    s3_key = f"bronze/atmospheric/nws_alerts/date={datetime.utcnow().strftime('%Y-%m-%d')}/alerts_{timestamp}.json"
    store_to_s3(processed_alerts, s3_key)

    # Also store by state for easier partitioning
    alerts_by_state = {}
    for alert in processed_alerts:
        area_desc = alert.get("areaDesc", "")
        # Simple state extraction (can be improved)
        for state in PRIORITY_STATES:
            if state in area_desc:
                if state not in alerts_by_state:
                    alerts_by_state[state] = []
                alerts_by_state[state].append(alert)
                stats["by_state"][state] = stats["by_state"].get(state, 0) + 1

    # Store partitioned by state
    for state, alerts in alerts_by_state.items():
        s3_key = f"bronze/atmospheric/nws_alerts/state={state}/date={datetime.utcnow().strftime('%Y-%m-%d')}/alerts_{timestamp}.json"
        store_to_s3(alerts, s3_key)

    logger.info(f"Alert ingestion complete: {stats}")
    return stats


def ingest_station_observations() -> Dict[str, int]:
    """
    Ingest latest observations from weather stations

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Station Observations ===")

    stats = {"total": 0, "successful": 0, "failed": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    all_observations = []

    for station_id in SAMPLE_STATIONS:
        logger.info(f"Fetching observations for station: {station_id}")

        # Get latest observation
        data = make_nws_request(f"/stations/{station_id}/observations/latest")

        if not data or "properties" not in data:
            logger.warning(f"No observation data for station {station_id}")
            stats["failed"] += 1
            continue

        props = data["properties"]

        # Extract observation data
        observation = {
            "station_id": station_id,
            "timestamp": props.get("timestamp"),
            "textDescription": props.get("textDescription"),
            "temperature": props.get("temperature", {}).get("value"),
            "temperature_unit": props.get("temperature", {}).get("unitCode"),
            "dewpoint": props.get("dewpoint", {}).get("value"),
            "windDirection": props.get("windDirection", {}).get("value"),
            "windSpeed": props.get("windSpeed", {}).get("value"),
            "windGust": props.get("windGust", {}).get("value"),
            "barometricPressure": props.get("barometricPressure", {}).get("value"),
            "seaLevelPressure": props.get("seaLevelPressure", {}).get("value"),
            "visibility": props.get("visibility", {}).get("value"),
            "relativeHumidity": props.get("relativeHumidity", {}).get("value"),
            "windChill": props.get("windChill", {}).get("value"),
            "heatIndex": props.get("heatIndex", {}).get("value"),
            "presentWeather": props.get("presentWeather"),
            "cloudLayers": props.get("cloudLayers"),
            "elevation": data.get("geometry", {}).get(
                "coordinates", [None, None, None]
            )[2],
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        all_observations.append(observation)
        stats["successful"] += 1
        stats["total"] += 1

        # Be nice to the API
        sleep(0.5)

    # Store to S3
    if all_observations:
        s3_key = f"bronze/atmospheric/nws_observations/date={datetime.utcnow().strftime('%Y-%m-%d')}/observations_{timestamp}.json"
        store_to_s3(all_observations, s3_key)

    logger.info(f"Observation ingestion complete: {stats}")
    return stats


def ingest_forecast_zones() -> Dict[str, int]:
    """
    Ingest forecast zone information

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Forecast Zones ===")

    stats = {"total": 0, "processed": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    all_zones = []

    # Get forecast zones for priority states
    for state in PRIORITY_STATES[:5]:  # Limit to first 5 states for MVP
        logger.info(f"Fetching forecast zones for state: {state}")

        data = make_nws_request(f"/zones", params={"area": state, "type": "forecast"})

        if not data or "features" not in data:
            logger.warning(f"No zone data for state {state}")
            continue

        features = data.get("features", [])
        logger.info(f"Retrieved {len(features)} zones for {state}")

        for feature in features:
            props = feature.get("properties", {})

            zone_record = {
                "zone_id": props.get("id"),
                "type": props.get("type"),
                "name": props.get("name"),
                "state": props.get("state"),
                "cwa": props.get("cwa"),  # County Warning Area
                "forecast_offices": props.get("forecastOffices"),
                "time_zone": props.get("timeZone"),
                "observation_stations": props.get("observationStations"),
                "geometry": feature.get("geometry"),
                "ingestion_timestamp": datetime.utcnow().isoformat(),
            }

            all_zones.append(zone_record)
            stats["processed"] += 1

        stats["total"] += len(features)
        sleep(1)  # Rate limiting

    # Store to S3
    if all_zones:
        s3_key = f"bronze/atmospheric/nws_forecast_zones/date={datetime.utcnow().strftime('%Y-%m-%d')}/zones_{timestamp}.json"
        store_to_s3(all_zones, s3_key)

    logger.info(f"Forecast zone ingestion complete: {stats}")
    return stats


def ingest_radar_stations() -> Dict[str, int]:
    """
    Ingest radar station metadata

    Returns:
        Statistics dict with counts
    """
    logger.info("=== Ingesting Radar Stations ===")

    stats = {"total": 0}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    data = make_nws_request("/radar/stations")

    if not data or "features" not in data:
        logger.warning("No radar station data retrieved")
        return stats

    features = data.get("features", [])
    stats["total"] = len(features)

    logger.info(f"Retrieved {len(features)} radar stations")

    # Process radar stations
    radar_stations = []
    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [None, None])

        station_record = {
            "station_id": props.get("id"),
            "name": props.get("name"),
            "type": props.get("stationType"),
            "elevation": props.get("elevation", {}).get("value"),
            "latitude": coords[1] if len(coords) > 1 else None,
            "longitude": coords[0] if len(coords) > 0 else None,
            "rda_elevation": props.get("rda", {}).get("elevation"),
            "timezone": props.get("timeZone"),
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        radar_stations.append(station_record)

    # Store to S3
    s3_key = f"bronze/atmospheric/nws_radar_stations/date={datetime.utcnow().strftime('%Y-%m-%d')}/stations_{timestamp}.json"
    store_to_s3(radar_stations, s3_key)

    logger.info(f"Radar station ingestion complete: {stats}")
    return stats


# =============================================================
# Main Execution
# =============================================================


def main():
    """Main execution flow"""

    logger.info("=" * 60)
    logger.info("Starting NWS Enhanced Data Ingestion")
    logger.info("=" * 60)

    start_time = datetime.utcnow()
    overall_stats = {
        "start_time": start_time.isoformat(),
        "alerts": {},
        "observations": {},
        "forecast_zones": {},
        "radar_stations": {},
    }

    try:
        # 1. Ingest Active Alerts
        overall_stats["alerts"] = ingest_active_alerts()

        # 2. Ingest Station Observations
        overall_stats["observations"] = ingest_station_observations()

        # 3. Ingest Forecast Zones
        overall_stats["forecast_zones"] = ingest_forecast_zones()

        # 4. Ingest Radar Stations
        overall_stats["radar_stations"] = ingest_radar_stations()

        # Calculate totals
        end_time = datetime.utcnow()
        overall_stats["end_time"] = end_time.isoformat()
        overall_stats["duration_seconds"] = (end_time - start_time).total_seconds()
        overall_stats["status"] = "SUCCESS"

        # Store job statistics
        stats_key = f"bronze/atmospheric/_job_stats/nws_ingestion_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        store_to_s3(overall_stats, stats_key)

        logger.info("=" * 60)
        logger.info("NWS Ingestion Complete!")
        logger.info(f"Duration: {overall_stats['duration_seconds']:.2f} seconds")
        logger.info(f"Alerts: {overall_stats['alerts'].get('total', 0)}")
        logger.info(
            f"Observations: {overall_stats['observations'].get('successful', 0)}"
        )
        logger.info(
            f"Forecast Zones: {overall_stats['forecast_zones'].get('total', 0)}"
        )
        logger.info(
            f"Radar Stations: {overall_stats['radar_stations'].get('total', 0)}"
        )
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error in NWS ingestion: {e}", exc_info=True)
        overall_stats["status"] = "FAILED"
        overall_stats["error"] = str(e)
        raise

    finally:
        # Commit job
        job.commit()


if __name__ == "__main__":
    main()
