#!/usr/bin/env python3
"""
NOAA Fire Data Portal Ingestion Lambda
Ingests wildfire detection data into Atmospheric Pond

Fetches near real-time wildfire detection data from NOAA's
Next Generation Fire System (NGFS) and stores it in the
atmospheric data pond.

Data Source: https://fire.data.nesdis.noaa.gov/
Pond: Atmospheric (fire is atmospheric/meteorological phenomenon)
Update Frequency: Every 15 minutes (EventBridge trigger)

Author: NOAA Data Lake Team
Version: 1.0
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import boto3
import requests
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")

# Configuration from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET", "noaa-federated-lake-899626030376-dev")
ENV = os.environ.get("ENV", "dev")
API_BASE_URL = "https://fire.data.nesdis.noaa.gov/api/ogc/detections/collections"

# Collections to ingest (prioritized order)
# Start with CONUS for broad coverage, add mesoscale if needed
COLLECTIONS = [
    {
        "id": "ngfs_schema.ngfs_detections_scene_west_conus",
        "name": "West CONUS",
        "priority": 1,
        "enabled": True,
    },
    {
        "id": "ngfs_schema.ngfs_detections_scene_east_conus",
        "name": "East CONUS",
        "priority": 1,
        "enabled": True,
    },
    # Mesoscale collections (optional - higher frequency, more cost)
    {
        "id": "ngfs_schema.ngfs_detections_scene_west_mesoscale1",
        "name": "West Mesoscale 1",
        "priority": 2,
        "enabled": False,
    },
    {
        "id": "ngfs_schema.ngfs_detections_scene_west_mesoscale2",
        "name": "West Mesoscale 2",
        "priority": 2,
        "enabled": False,
    },
    {
        "id": "ngfs_schema.ngfs_detections_scene_east_mesoscale1",
        "name": "East Mesoscale 1",
        "priority": 2,
        "enabled": False,
    },
    {
        "id": "ngfs_schema.ngfs_detections_scene_east_mesoscale2",
        "name": "East Mesoscale 2",
        "priority": 2,
        "enabled": False,
    },
]


def get_last_ingestion_time(collection_id: str) -> str:
    """
    Get last successful ingestion timestamp from SSM Parameter Store

    Args:
        collection_id: Fire collection identifier

    Returns:
        ISO 8601 timestamp string
    """
    param_name = f"/noaa/{ENV}/atmospheric/fire/last_ingestion/{collection_id}"

    try:
        response = ssm_client.get_parameter(Name=param_name)
        timestamp = response["Parameter"]["Value"]
        logger.info(f"Last ingestion for {collection_id}: {timestamp}")
        return timestamp
    except ssm_client.exceptions.ParameterNotFound:
        # First run - get data from last 1 hour
        timestamp = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        logger.info(
            f"No previous ingestion found for {collection_id}, using: {timestamp}"
        )
        return timestamp
    except Exception as e:
        logger.error(f"Error getting last ingestion time: {e}")
        # Fallback to last hour
        return (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"


def set_last_ingestion_time(collection_id: str, timestamp: str) -> bool:
    """
    Save successful ingestion timestamp to SSM Parameter Store

    Args:
        collection_id: Fire collection identifier
        timestamp: ISO 8601 timestamp string

    Returns:
        True if successful, False otherwise
    """
    param_name = f"/noaa/{ENV}/atmospheric/fire/last_ingestion/{collection_id}"

    try:
        ssm_client.put_parameter(
            Name=param_name,
            Value=timestamp,
            Type="String",
            Overwrite=True,
            Description=f"Last successful ingestion for {collection_id}",
        )
        logger.info(f"Updated last ingestion time for {collection_id}: {timestamp}")
        return True
    except Exception as e:
        logger.error(f"Error setting last ingestion time: {e}")
        return False


def fetch_fire_detections(
    collection_id: str, start_time: str, end_time: str, limit: int = 1000
) -> Tuple[List[Dict], Dict]:
    """
    Fetch fire detections from NOAA Fire Data Portal API
    Handles pagination automatically

    Args:
        collection_id: Fire collection to query
        start_time: Start timestamp (ISO 8601)
        end_time: End timestamp (ISO 8601)
        limit: Results per page (max 1000)

    Returns:
        Tuple of (features list, metadata dict)
    """
    url = f"{API_BASE_URL}/{collection_id}/items"
    all_features = []
    offset = 0
    page_count = 0

    params = {
        "datetime": f"{start_time}/{end_time}",
        "limit": limit,
        "offset": offset,
    }

    logger.info(f"Fetching fire data from: {collection_id}")
    logger.info(f"Time range: {start_time} to {end_time}")

    while True:
        page_count += 1

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            all_features.extend(features)

            number_matched = data.get("numberMatched", 0)
            number_returned = data.get("numberReturned", 0)

            logger.info(
                f"Page {page_count}: Retrieved {number_returned} detections "
                f"(offset: {offset}, total matched: {number_matched})"
            )

            # Check if there are more pages
            if offset + number_returned >= number_matched or number_returned == 0:
                break

            # Move to next page
            offset += limit
            params["offset"] = offset

            # Safety limit on pages
            if page_count >= 100:
                logger.warning(f"Reached page limit (100), stopping pagination")
                break

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching page {page_count}")
            break
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page_count}: {e}")
            break
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response on page {page_count}: {e}")
            break

    metadata = {
        "total_features": len(all_features),
        "pages_fetched": page_count,
        "collection_id": collection_id,
        "time_range": {"start": start_time, "end": end_time},
    }

    logger.info(
        f"Fetch complete: {len(all_features)} total detections from {page_count} pages"
    )

    return all_features, metadata


def save_to_bronze(
    features: List[Dict], metadata: Dict, collection_id: str, timestamp: str
) -> bool:
    """
    Save raw fire data to S3 Bronze layer in atmospheric pond

    Args:
        features: List of GeoJSON features
        metadata: Fetch metadata
        collection_id: Fire collection identifier
        timestamp: Ingestion timestamp

    Returns:
        True if successful, False otherwise
    """
    if not features:
        logger.info("No features to save, skipping Bronze write")
        return True

    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    # Collection name for path (remove schema prefix)
    collection_name = collection_id.replace("ngfs_schema.ngfs_detections_scene_", "")

    # Bronze layer path: bronze/atmospheric/fire/{collection}/YYYY/MM/DD/HH/
    key = (
        f"bronze/atmospheric/fire/{collection_name}/"
        f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/"
        f"hour={dt.hour:02d}/fire_{dt.strftime('%Y%m%d_%H%M%S')}.json"
    )

    # Construct GeoJSON FeatureCollection
    data = {
        "type": "FeatureCollection",
        "collection": collection_id,
        "ingestion_timestamp": timestamp,
        "time_range": metadata["time_range"],
        "numberReturned": len(features),
        "metadata": {
            "pages_fetched": metadata["pages_fetched"],
            "data_source": "NOAA NESDIS Fire Data Portal",
            "api_version": "OGC Features API",
        },
        "features": features,
    }

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType="application/json",
            Metadata={
                "collection": collection_id,
                "ingestion_time": timestamp,
                "record_count": str(len(features)),
                "data_type": "fire_detections",
                "pond": "atmospheric",
            },
        )
        logger.info(f"✓ Saved to Bronze: s3://{S3_BUCKET}/{key}")
        logger.info(f"  - Records: {len(features)}")
        logger.info(f"  - Size: {len(json.dumps(data)) / 1024:.2f} KB")
        return True

    except ClientError as e:
        logger.error(f"S3 error saving to Bronze: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving to Bronze: {e}")
        return False


def aggregate_to_gold(features: List[Dict], collection_id: str, timestamp: str) -> bool:
    """
    Aggregate fire detection data and save to Gold layer
    Creates summary statistics and incident aggregations

    Args:
        features: List of GeoJSON features
        collection_id: Fire collection identifier
        timestamp: Ingestion timestamp

    Returns:
        True if successful, False otherwise
    """
    if not features:
        logger.info("No features to aggregate, skipping Gold write")
        return True

    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    date_str = dt.strftime("%Y-%m-%d")

    # Extract collection name
    collection_name = collection_id.replace("ngfs_schema.ngfs_detections_scene_", "")

    # Aggregate by incident name
    incidents = {}
    detections_by_intensity = {"low": 0, "medium": 0, "high": 0, "extreme": 0}
    total_detections = 0

    for feature in features:
        props = feature.get("properties", {})

        # Count by intensity
        frp = props.get("frp", 0)
        if frp < 10:
            detections_by_intensity["low"] += 1
        elif frp < 50:
            detections_by_intensity["medium"] += 1
        elif frp < 100:
            detections_by_intensity["high"] += 1
        else:
            detections_by_intensity["extreme"] += 1

        total_detections += 1

        # Aggregate by incident name
        incident_name = props.get("known_incident_name")
        if incident_name:
            if incident_name not in incidents:
                coords = feature.get("geometry", {}).get("coordinates", [0, 0])
                incidents[incident_name] = {
                    "incident_name": incident_name,
                    "detection_count": 0,
                    "max_frp": 0,
                    "min_frp": float("inf"),
                    "total_frp": 0,
                    "latitudes": [],
                    "longitudes": [],
                    "first_seen": props.get("acq_date_time"),
                    "last_seen": props.get("acq_date_time"),
                    "satellites": set(),
                    "confidence_levels": set(),
                }

            incident = incidents[incident_name]
            incident["detection_count"] += 1
            incident["max_frp"] = max(incident["max_frp"], frp)
            incident["min_frp"] = min(incident["min_frp"], frp)
            incident["total_frp"] += frp

            coords = feature.get("geometry", {}).get("coordinates", [0, 0])
            incident["latitudes"].append(
                coords[1] if len(coords) > 1 else props.get("latitude", 0)
            )
            incident["longitudes"].append(
                coords[0] if len(coords) > 0 else props.get("longitude", 0)
            )

            incident["satellites"].add(props.get("satellite", "unknown"))
            incident["confidence_levels"].add(props.get("confidence", "unknown"))

            # Update time range
            acq_time = props.get("acq_date_time")
            if acq_time:
                if acq_time < incident["first_seen"]:
                    incident["first_seen"] = acq_time
                if acq_time > incident["last_seen"]:
                    incident["last_seen"] = acq_time

    # Calculate incident summaries
    incident_summaries = []
    for incident_name, incident_data in incidents.items():
        # Calculate center point
        lats = incident_data["latitudes"]
        lons = incident_data["longitudes"]

        summary = {
            "incident_name": incident_name,
            "detection_count": incident_data["detection_count"],
            "max_frp_mw": incident_data["max_frp"],
            "min_frp_mw": incident_data["min_frp"],
            "avg_frp_mw": incident_data["total_frp"] / incident_data["detection_count"],
            "center_latitude": sum(lats) / len(lats) if lats else 0,
            "center_longitude": sum(lons) / len(lons) if lons else 0,
            "first_detection": incident_data["first_seen"],
            "last_detection": incident_data["last_seen"],
            "satellites": list(incident_data["satellites"]),
            "confidence_levels": list(incident_data["confidence_levels"]),
        }
        incident_summaries.append(summary)

    # Create Gold layer summary
    gold_data = {
        "date": date_str,
        "timestamp": timestamp,
        "collection": collection_name,
        "summary": {
            "total_detections": total_detections,
            "named_incidents": len(incidents),
            "unnamed_detections": total_detections
            - sum(i["detection_count"] for i in incidents.values()),
            "detections_by_intensity": detections_by_intensity,
        },
        "incidents": incident_summaries,
    }

    # Gold layer path
    key = f"gold/atmospheric/fire/date={date_str}/fire_summary_{collection_name}_{dt.strftime('%Y%m%d_%H%M%S')}.json"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(gold_data, indent=2),
            ContentType="application/json",
            Metadata={
                "collection": collection_id,
                "date": date_str,
                "total_detections": str(total_detections),
                "named_incidents": str(len(incidents)),
                "data_type": "fire_summary",
                "pond": "atmospheric",
            },
        )
        logger.info(f"✓ Saved to Gold: s3://{S3_BUCKET}/{key}")
        logger.info(f"  - Total detections: {total_detections}")
        logger.info(f"  - Named incidents: {len(incidents)}")
        logger.info(f"  - Intensity breakdown: {detections_by_intensity}")
        return True

    except Exception as e:
        logger.error(f"Error saving to Gold: {e}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler
    Fetches fire detection data from NOAA Fire Portal and stores in atmospheric pond

    Args:
        event: Lambda event (EventBridge scheduled event)
        context: Lambda context

    Returns:
        Response dict with status and details
    """
    logger.info("=" * 60)
    logger.info("NOAA Fire Data Ingestion - Atmospheric Pond")
    logger.info("=" * 60)
    logger.info(f"Environment: {ENV}")
    logger.info(f"S3 Bucket: {S3_BUCKET}")
    logger.info(f"Triggered by: {event.get('source', 'manual')}")

    results = {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": ENV,
        "collections_processed": {},
        "total_detections": 0,
        "total_incidents": 0,
    }

    end_time = datetime.utcnow()
    end_time_str = end_time.isoformat() + "Z"

    # Process only enabled collections
    enabled_collections = [c for c in COLLECTIONS if c["enabled"]]

    logger.info(f"Processing {len(enabled_collections)} enabled collections")
    logger.info("-" * 60)

    for collection in enabled_collections:
        collection_id = collection["id"]
        collection_name = collection["name"]

        logger.info(f"\nProcessing: {collection_name} ({collection_id})")

        try:
            # Get last ingestion time
            start_time_str = get_last_ingestion_time(collection_id)

            # Fetch fire detections
            features, metadata = fetch_fire_detections(
                collection_id, start_time_str, end_time_str
            )

            if features:
                # Save to Bronze layer
                bronze_success = save_to_bronze(
                    features, metadata, collection_id, end_time_str
                )

                # Aggregate to Gold layer
                gold_success = aggregate_to_gold(features, collection_id, end_time_str)

                if bronze_success and gold_success:
                    # Update last ingestion time only if both layers succeeded
                    set_last_ingestion_time(collection_id, end_time_str)

                    # Count incidents
                    incident_count = len(
                        set(
                            f.get("properties", {}).get("known_incident_name")
                            for f in features
                            if f.get("properties", {}).get("known_incident_name")
                        )
                    )

                    results["collections_processed"][collection_name] = {
                        "status": "success",
                        "detections": len(features),
                        "incidents": incident_count,
                        "pages": metadata["pages_fetched"],
                    }

                    results["total_detections"] += len(features)
                    results["total_incidents"] += incident_count

                    logger.info(f"✓ Successfully processed {collection_name}")
                else:
                    results["collections_processed"][collection_name] = {
                        "status": "partial",
                        "error": "Failed to save to Bronze or Gold",
                    }
                    results["status"] = "partial_success"
            else:
                # No new detections - this is normal
                results["collections_processed"][collection_name] = {
                    "status": "success",
                    "detections": 0,
                    "message": "No new fire detections in time range",
                }
                logger.info(f"✓ No new detections for {collection_name}")

                # Still update last ingestion time
                set_last_ingestion_time(collection_id, end_time_str)

        except Exception as e:
            logger.error(f"✗ Error processing {collection_name}: {e}", exc_info=True)
            results["collections_processed"][collection_name] = {
                "status": "error",
                "error": str(e),
            }
            results["status"] = "partial_success"

    logger.info("=" * 60)
    logger.info("Fire Data Ingestion Complete")
    logger.info("=" * 60)
    logger.info(f"Total detections: {results['total_detections']}")
    logger.info(f"Total incidents: {results['total_incidents']}")
    logger.info(f"Collections processed: {len(results['collections_processed'])}")
    logger.info(f"Status: {results['status']}")
    logger.info("=" * 60)

    return {
        "statusCode": 200 if results["status"] == "success" else 207,
        "body": json.dumps(results, indent=2),
    }


# For local testing
if __name__ == "__main__":
    # Simulate Lambda event
    test_event = {
        "source": "manual-test",
        "time": datetime.utcnow().isoformat() + "Z",
    }

    test_context = type(
        "Context",
        (),
        {
            "function_name": "noaa-ingest-fire-dev",
            "memory_limit_in_mb": 512,
            "invoked_function_arn": "arn:aws:lambda:us-east-1:899626030376:function:noaa-ingest-fire-dev",
            "aws_request_id": "test-request-id",
        },
    )()

    result = lambda_handler(test_event, test_context)
    print("\n" + "=" * 60)
    print("Test Result:")
    print("=" * 60)
    print(json.dumps(json.loads(result["body"]), indent=2))
