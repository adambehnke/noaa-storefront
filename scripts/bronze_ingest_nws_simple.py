#!/usr/bin/env python3
"""
Simplified NWS Data Ingestion for AWS Glue Python Shell
Ingests weather data from NWS API into Bronze layer

No Spark dependencies - pure Python with boto3 and requests
"""

import sys
import os
import json
import boto3
import requests
from datetime import datetime, timezone
from time import sleep

# Parse command line arguments using Glue getResolvedOptions
try:
    from awsglue.utils import getResolvedOptions

    args = getResolvedOptions(sys.argv, ["LAKE_BUCKET", "ENV"])
    LAKE_BUCKET = args["LAKE_BUCKET"]
    ENV = args["ENV"]
except Exception as e:
    # Fallback for local testing
    LAKE_BUCKET = os.getenv("LAKE_BUCKET")
    ENV = os.getenv("ENV", "dev")
    if not LAKE_BUCKET:
        print(f"ERROR: LAKE_BUCKET is required. Error: {e}")
        sys.exit(1)

print(f"Starting NWS ingestion for environment: {ENV}")
print(f"Target bucket: {LAKE_BUCKET}")

# Configuration
NWS_BASE_URL = "https://api.weather.gov"
NWS_USER_AGENT = "NOAA-Federated-Data-Lake/1.0"
REQUEST_TIMEOUT = 15
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2

# Sample stations
SAMPLE_STATIONS = ["KSFO", "KLAX", "KJFK", "KORD", "KATL", "KDFW"]

# AWS client
s3_client = boto3.client("s3")


def make_nws_request(endpoint, params=None):
    """Make HTTP request to NWS API with retry logic"""
    url = f"{NWS_BASE_URL}{endpoint}"
    headers = {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}

    for attempt in range(RETRY_ATTEMPTS):
        try:
            print(f"  Requesting: {endpoint} (attempt {attempt + 1})")
            response = requests.get(
                url, headers=headers, params=params, timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"  Rate limited, waiting {RETRY_DELAY * (attempt + 1)}s")
                sleep(RETRY_DELAY * (attempt + 1))
                continue
            else:
                print(f"  HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"  Request failed: {e}")

        if attempt < RETRY_ATTEMPTS - 1:
            sleep(RETRY_DELAY)

    return None


def store_to_s3(data, s3_key):
    """Store data to S3 as JSON"""
    try:
        json_data = json.dumps(data, default=str)

        s3_client.put_object(
            Bucket=LAKE_BUCKET,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json",
            Metadata={
                "ingestion_timestamp": datetime.utcnow().isoformat(),
                "source": "nws_api",
                "environment": ENV,
            },
        )

        print(f"  ✓ Stored to s3://{LAKE_BUCKET}/{s3_key}")
        return True

    except Exception as e:
        print(f"  ✗ Failed to store to S3: {e}")
        return False


def ingest_active_alerts():
    """Ingest active weather alerts"""
    print("\n=== Ingesting Active Alerts ===")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    data = make_nws_request("/alerts/active")

    if not data or "features" not in data:
        print("  No alert data retrieved")
        return 0

    features = data.get("features", [])
    print(f"  Retrieved {len(features)} active alerts")

    # Process alerts
    processed_alerts = []
    for feature in features:
        props = feature.get("properties", {})
        alert_record = {
            "id": props.get("id"),
            "event": props.get("event"),
            "severity": props.get("severity"),
            "certainty": props.get("certainty"),
            "urgency": props.get("urgency"),
            "headline": props.get("headline"),
            "areaDesc": props.get("areaDesc"),
            "onset": props.get("onset"),
            "expires": props.get("expires"),
            "status": props.get("status"),
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }
        processed_alerts.append(alert_record)

    # Store to S3
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    s3_key = f"bronze/atmospheric/nws_alerts/date={date_str}/alerts_{timestamp}.json"
    store_to_s3(processed_alerts, s3_key)

    return len(processed_alerts)


def ingest_station_observations():
    """Ingest latest observations from weather stations"""
    print("\n=== Ingesting Station Observations ===")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    all_observations = []

    for station_id in SAMPLE_STATIONS:
        print(f"  Fetching observations for station: {station_id}")

        data = make_nws_request(f"/stations/{station_id}/observations/latest")

        if not data or "properties" not in data:
            print(f"    No data for station {station_id}")
            continue

        props = data["properties"]
        observation = {
            "station_id": station_id,
            "timestamp": props.get("timestamp"),
            "textDescription": props.get("textDescription"),
            "temperature": props.get("temperature", {}).get("value"),
            "dewpoint": props.get("dewpoint", {}).get("value"),
            "windSpeed": props.get("windSpeed", {}).get("value"),
            "windDirection": props.get("windDirection", {}).get("value"),
            "barometricPressure": props.get("barometricPressure", {}).get("value"),
            "visibility": props.get("visibility", {}).get("value"),
            "relativeHumidity": props.get("relativeHumidity", {}).get("value"),
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        all_observations.append(observation)
        sleep(0.5)  # Rate limiting

    # Store to S3
    if all_observations:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"bronze/atmospheric/nws_observations/date={date_str}/observations_{timestamp}.json"
        store_to_s3(all_observations, s3_key)

    return len(all_observations)


def main():
    """Main execution"""
    print("=" * 60)
    print("Starting NWS Data Ingestion")
    print("=" * 60)

    start_time = datetime.utcnow()
    stats = {"start_time": start_time.isoformat(), "alerts": 0, "observations": 0}

    try:
        # Ingest active alerts
        stats["alerts"] = ingest_active_alerts()

        # Ingest station observations
        stats["observations"] = ingest_station_observations()

        # Calculate totals
        end_time = datetime.utcnow()
        stats["end_time"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        stats["status"] = "SUCCESS"

        # Store job statistics
        stats_key = f"bronze/atmospheric/_job_stats/nws_ingestion_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        store_to_s3(stats, stats_key)

        print("\n" + "=" * 60)
        print("NWS Ingestion Complete!")
        print(f"Duration: {stats['duration_seconds']:.2f} seconds")
        print(f"Alerts: {stats['alerts']}")
        print(f"Observations: {stats['observations']}")
        print("=" * 60)

        sys.exit(0)

    except Exception as e:
        print(f"\nFatal error: {e}")
        stats["status"] = "FAILED"
        stats["error"] = str(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
