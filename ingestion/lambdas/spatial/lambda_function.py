"""
NOAA Spatial Data Ingestion Lambda
Implements Medallion Architecture: Bronze -> Silver -> Gold
Ingests geographic and spatial reference data from NOAA
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
import requests

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
s3_client = boto3.client("s3")
glue_client = boto3.client("glue")
athena_client = boto3.client("athena")

# Environment variables
ENV = os.environ.get("ENV", "dev")
BUCKET_NAME = os.environ.get("BUCKET_NAME", f"noaa-data-lake-{ENV}")
DATABASE_NAME = f"noaa_federated_{ENV}"

# NOAA Spatial Data Endpoints
NOAA_WEATHER_API = "https://api.weather.gov"
NOAA_ZONES_URL = f"{NOAA_WEATHER_API}/zones"
NOAA_POINTS_URL = f"{NOAA_WEATHER_API}/points"

# Geographic areas of interest (major US cities)
MAJOR_US_LOCATIONS = [
    {"name": "Boston", "lat": 42.3601, "lon": -71.0589},
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "Philadelphia", "lat": 39.9526, "lon": -75.1652},
    {"name": "Washington DC", "lat": 38.9072, "lon": -77.0369},
    {"name": "Atlanta", "lat": 33.7490, "lon": -84.3880},
    {"name": "Miami", "lat": 25.7617, "lon": -80.1918},
    {"name": "Chicago", "lat": 41.8781, "lon": -87.6298},
    {"name": "Dallas", "lat": 32.7767, "lon": -96.7970},
    {"name": "Denver", "lat": 39.7392, "lon": -104.9903},
    {"name": "Phoenix", "lat": 33.4484, "lon": -112.0740},
    {"name": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
    {"name": "San Francisco", "lat": 37.7749, "lon": -122.4194},
    {"name": "Seattle", "lat": 47.6062, "lon": -122.3321},
    {"name": "Portland", "lat": 45.5152, "lon": -122.6784},
    {"name": "Las Vegas", "lat": 36.1699, "lon": -115.1398},
    {"name": "Houston", "lat": 29.7604, "lon": -95.3698},
    {"name": "San Diego", "lat": 32.7157, "lon": -117.1611},
]

# Zone types
ZONE_TYPES = ["land", "marine", "forecast", "county", "fire", "public"]


class SpatialIngestion:
    """Handles spatial data ingestion with medallion architecture"""

    def __init__(self, mode="incremental"):
        self.mode = mode
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "NOAA-Federated-Data-Lake/1.0 (contact@example.com)",
                "Accept": "application/geo+json",
            }
        )
        self.ingestion_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.stats = {
            "bronze_records": 0,
            "silver_records": 0,
            "gold_records": 0,
            "errors": 0,
            "apis_called": 0,
        }

    def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """Fetch data from NOAA API with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                self.stats["apis_called"] += 1

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = 2**attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"API returned {response.status_code}: {url}")
                    return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                else:
                    self.stats["errors"] += 1
                    return None
        return None

    def ingest_weather_zones(self) -> List[Dict]:
        """Ingest weather zone boundaries and metadata"""
        records = []

        for zone_type in ZONE_TYPES:
            try:
                url = f"{NOAA_ZONES_URL}?type={zone_type}"
                data = self.fetch_with_retry(url)

                if not data or "features" not in data:
                    continue

                for feature in data["features"]:
                    try:
                        props = feature.get("properties", {})
                        geom = feature.get("geometry")

                        record = {
                            "record_id": hashlib.md5(
                                f"{props.get('id')}_{zone_type}".encode()
                            ).hexdigest(),
                            "zone_id": props.get("id"),
                            "zone_type": zone_type,
                            "name": props.get("name"),
                            "state": props.get("state"),
                            "cwa": props.get("cwa"),  # County Warning Area
                            "forecast_offices": json.dumps(
                                props.get("forecastOffices", [])
                            ),
                            "time_zone": json.dumps(props.get("timeZone", [])),
                            "observation_stations": json.dumps(
                                props.get("observationStations", [])
                            ),
                            "geometry_type": geom.get("type") if geom else None,
                            "geometry": json.dumps(geom) if geom else None,
                            "ingestion_timestamp": datetime.utcnow().isoformat(),
                            "ingestion_id": self.ingestion_id,
                            "data_source": "NOAA_Weather_API",
                            "raw_json": json.dumps(feature),
                        }
                        records.append(record)
                    except Exception as e:
                        logger.error(f"Error processing zone feature: {str(e)}")
                        self.stats["errors"] += 1

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error ingesting {zone_type} zones: {str(e)}")
                self.stats["errors"] += 1

        return records

    def ingest_location_metadata(self) -> List[Dict]:
        """Ingest spatial metadata for major locations"""
        records = []

        for location in MAJOR_US_LOCATIONS:
            try:
                lat = location["lat"]
                lon = location["lon"]
                url = f"{NOAA_POINTS_URL}/{lat},{lon}"

                data = self.fetch_with_retry(url)
                if not data or "properties" not in data:
                    continue

                props = data["properties"]
                geom = data.get("geometry")

                record = {
                    "record_id": hashlib.md5(
                        f"{location['name']}_{lat}_{lon}".encode()
                    ).hexdigest(),
                    "location_name": location["name"],
                    "latitude": lat,
                    "longitude": lon,
                    "cwa": props.get("cwa"),
                    "forecast_office": props.get("forecastOffice"),
                    "grid_id": props.get("gridId"),
                    "grid_x": props.get("gridX"),
                    "grid_y": props.get("gridY"),
                    "forecast_url": props.get("forecast"),
                    "forecast_hourly_url": props.get("forecastHourly"),
                    "forecast_grid_data_url": props.get("forecastGridData"),
                    "observation_stations_url": props.get("observationStations"),
                    "county": props.get("county"),
                    "fire_weather_zone": props.get("fireWeatherZone"),
                    "time_zone": props.get("timeZone"),
                    "radar_station": props.get("radarStation"),
                    "geometry": json.dumps(geom) if geom else None,
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_Weather_API",
                    "raw_json": json.dumps(data),
                }
                records.append(record)

                # Rate limiting
                time.sleep(0.3)

            except Exception as e:
                logger.error(f"Error ingesting location {location['name']}: {str(e)}")
                self.stats["errors"] += 1

        return records

    def ingest_marine_zones(self) -> List[Dict]:
        """Ingest marine zone boundaries"""
        records = []

        try:
            url = f"{NOAA_ZONES_URL}?type=marine"
            data = self.fetch_with_retry(url)

            if not data or "features" not in data:
                return records

            for feature in data["features"]:
                try:
                    props = feature.get("properties", {})
                    geom = feature.get("geometry")

                    record = {
                        "record_id": hashlib.md5(
                            f"marine_{props.get('id')}".encode()
                        ).hexdigest(),
                        "zone_id": props.get("id"),
                        "zone_type": "marine",
                        "name": props.get("name"),
                        "state": props.get("state"),
                        "cwa": props.get("cwa"),
                        "forecast_offices": json.dumps(
                            props.get("forecastOffices", [])
                        ),
                        "observation_stations": json.dumps(
                            props.get("observationStations", [])
                        ),
                        "geometry_type": geom.get("type") if geom else None,
                        "geometry": json.dumps(geom) if geom else None,
                        "ingestion_timestamp": datetime.utcnow().isoformat(),
                        "ingestion_id": self.ingestion_id,
                        "data_source": "NOAA_Weather_API",
                        "raw_json": json.dumps(feature),
                    }
                    records.append(record)
                except Exception as e:
                    logger.error(f"Error processing marine zone: {str(e)}")
                    self.stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error ingesting marine zones: {str(e)}")
            self.stats["errors"] += 1

        return records

    def write_bronze_layer(self, records: List[Dict], data_type: str):
        """Write raw data to Bronze layer (S3)"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}/hour={timestamp.hour:02d}"
        key = f"bronze/spatial/{data_type}/{partition}/data_{self.ingestion_id}.json"

        try:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=json.dumps(records, indent=2),
                ContentType="application/json",
            )
            self.stats["bronze_records"] += len(records)
            logger.info(f"Wrote {len(records)} records to Bronze: {key}")
        except Exception as e:
            logger.error(f"Error writing to Bronze layer: {str(e)}")
            self.stats["errors"] += 1

    def process_silver_layer(
        self, bronze_records: List[Dict], data_type: str
    ) -> List[Dict]:
        """Clean and validate data for Silver layer"""
        silver_records = []

        for record in bronze_records:
            try:
                # Remove raw JSON
                cleaned = {k: v for k, v in record.items() if k != "raw_json"}

                # Validate coordinates
                if cleaned.get("latitude") and cleaned.get("longitude"):
                    lat = cleaned["latitude"]
                    lon = cleaned["longitude"]
                    cleaned["coordinates_valid"] = (
                        -90 <= lat <= 90 and -180 <= lon <= 180
                    )

                # Add geographic region
                if cleaned.get("latitude"):
                    lat = cleaned["latitude"]
                    if lat >= 40:
                        cleaned["region"] = "northern"
                    elif lat >= 30:
                        cleaned["region"] = "mid"
                    else:
                        cleaned["region"] = "southern"

                if cleaned.get("longitude"):
                    lon = cleaned["longitude"]
                    if lon < -100:
                        cleaned["coast"] = "west"
                    elif lon < -80:
                        cleaned["coast"] = "mid"
                    else:
                        cleaned["coast"] = "east"

                # Zone metadata flags
                cleaned["has_geometry"] = cleaned.get("geometry") is not None
                cleaned["has_forecast_office"] = (
                    cleaned.get("forecast_office") is not None
                    or cleaned.get("cwa") is not None
                )
                cleaned["is_marine"] = cleaned.get("zone_type") == "marine"
                cleaned["is_coastal"] = (
                    "coastal" in str(cleaned.get("name", "")).lower()
                    or "offshore" in str(cleaned.get("name", "")).lower()
                )

                silver_records.append(cleaned)

            except Exception as e:
                logger.error(f"Error processing Silver record: {str(e)}")
                self.stats["errors"] += 1

        return silver_records

    def write_silver_layer(self, records: List[Dict], data_type: str):
        """Write cleaned data to Silver layer"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = (
            f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}"
        )
        key = f"silver/spatial/{data_type}/{partition}/data_{self.ingestion_id}.json"

        try:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=json.dumps(records, indent=2),
                ContentType="application/json",
            )
            self.stats["silver_records"] += len(records)
            logger.info(f"Wrote {len(records)} records to Silver: {key}")
        except Exception as e:
            logger.error(f"Error writing to Silver layer: {str(e)}")
            self.stats["errors"] += 1

    def process_gold_layer(
        self, silver_records: List[Dict], data_type: str
    ) -> List[Dict]:
        """Aggregate and enrich data for Gold layer"""
        # For spatial data, Gold layer is mostly same as Silver
        # but with additional indexing and grouping metadata
        gold_records = []

        for record in silver_records:
            try:
                gold_record = record.copy()

                # Add search/query optimizations
                if record.get("name"):
                    gold_record["name_lower"] = record["name"].lower()
                    gold_record["name_tokens"] = record["name"].lower().split()

                # Add spatial index hints (for future spatial queries)
                if record.get("latitude") and record.get("longitude"):
                    lat = record["latitude"]
                    lon = record["longitude"]

                    # Grid cell (1 degree precision)
                    gold_record["grid_lat"] = int(lat)
                    gold_record["grid_lon"] = int(lon)

                    # Geohash-like identifier (simplified)
                    gold_record["spatial_key"] = f"{int(lat)}_{int(lon)}"

                gold_records.append(gold_record)

            except Exception as e:
                logger.error(f"Error processing Gold record: {str(e)}")
                self.stats["errors"] += 1

        return gold_records

    def write_gold_layer(self, records: List[Dict], data_type: str):
        """Write aggregated data to Gold layer (queryable via Athena)"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = (
            f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}"
        )
        key = f"gold/spatial/{data_type}/{partition}/data_{self.ingestion_id}.json"

        try:
            # Convert list fields to JSON strings for Athena
            for record in records:
                if "name_tokens" in record and isinstance(record["name_tokens"], list):
                    record["name_tokens"] = json.dumps(record["name_tokens"])

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=json.dumps(records, indent=2),
                ContentType="application/json",
            )
            self.stats["gold_records"] += len(records)
            logger.info(f"Wrote {len(records)} records to Gold: {key}")
        except Exception as e:
            logger.error(f"Error writing to Gold layer: {str(e)}")
            self.stats["errors"] += 1

    def run_ingestion(self):
        """Main ingestion workflow"""
        logger.info(f"Starting spatial ingestion - Mode: {self.mode}")
        start_time = time.time()

        # 1. Ingest weather zones
        logger.info("Ingesting weather zones...")
        zones = self.ingest_weather_zones()
        if zones:
            self.write_bronze_layer(zones, "zones")
            silver_zones = self.process_silver_layer(zones, "zones")
            self.write_silver_layer(silver_zones, "zones")
            gold_zones = self.process_gold_layer(silver_zones, "zones")
            self.write_gold_layer(gold_zones, "zones")

        # 2. Ingest location metadata
        logger.info("Ingesting location metadata...")
        locations = self.ingest_location_metadata()
        if locations:
            self.write_bronze_layer(locations, "locations")
            silver_locations = self.process_silver_layer(locations, "locations")
            self.write_silver_layer(silver_locations, "locations")
            gold_locations = self.process_gold_layer(silver_locations, "locations")
            self.write_gold_layer(gold_locations, "locations")

        # 3. Ingest marine zones
        logger.info("Ingesting marine zones...")
        marine_zones = self.ingest_marine_zones()
        if marine_zones:
            self.write_bronze_layer(marine_zones, "marine_zones")
            silver_marine = self.process_silver_layer(marine_zones, "marine_zones")
            self.write_silver_layer(silver_marine, "marine_zones")
            gold_marine = self.process_gold_layer(silver_marine, "marine_zones")
            self.write_gold_layer(gold_marine, "marine_zones")

        duration = time.time() - start_time
        logger.info(
            f"Ingestion complete in {duration:.2f}s - Stats: {json.dumps(self.stats)}"
        )

        return self.stats


def lambda_handler(event, context):
    """Lambda entry point"""
    try:
        # Parse event parameters
        mode = event.get("mode", "incremental")

        logger.info(f"Lambda invoked - Mode: {mode}")

        # Run ingestion
        ingestion = SpatialIngestion(mode=mode)
        stats = ingestion.run_ingestion()

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "mode": mode,
                    "ingestion_id": ingestion.ingestion_id,
                    "stats": stats,
                    "message": f"Ingested {stats['bronze_records']} bronze, {stats['silver_records']} silver, {stats['gold_records']} gold records",
                }
            ),
        }

    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "error": str(e)}),
        }
