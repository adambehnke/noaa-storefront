"""
NOAA Oceanic Data Ingestion Lambda
Implements Medallion Architecture: Bronze -> Silver -> Gold
Ingests current and historical oceanic data from NOAA CO-OPS and other endpoints
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
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

# NOAA CO-OPS API Configuration
COOPS_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# Major US coastal stations for comprehensive coverage
MAJOR_OCEAN_STATIONS = [
    "8454000",  # Providence, RI
    "8443970",  # Boston, MA
    "8518750",  # The Battery, NY
    "8551910",  # Cape May, NJ
    "8557380",  # Lewes, DE
    "8594900",  # Baltimore, MD
    "8632200",  # Kiptopeke, VA
    "8638610",  # Sewells Point, VA
    "8651370",  # Duck, NC
    "8652587",  # Oregon Inlet Marina, NC
    "8656483",  # Beaufort, NC
    "8658120",  # Wilmington, NC
    "8661070",  # Springmaid Pier, SC
    "8665530",  # Charleston, SC
    "8670870",  # Fort Pulaski, GA
    "8720218",  # Mayport, FL
    "8721604",  # Trident Pier, FL
    "8723970",  # Vaca Key, FL
    "8724580",  # Key West, FL
    "8725110",  # Naples, FL
    "8726520",  # St. Petersburg, FL
    "8726724",  # Clearwater Beach, FL
    "8727520",  # Cedar Key, FL
    "8729108",  # Panama City, FL
    "8729840",  # Pensacola, FL
    "8735180",  # Dauphin Island, AL
    "8760922",  # Pilots Station East, LA
    "8761724",  # Grand Isle, LA
    "8764227",  # LAWMA, LA
    "8770570",  # Sabine Pass North, TX
    "8771450",  # Galveston Pier 21, TX
    "8775870",  # Corpus Christi, TX
    "8779770",  # Port Isabel, TX
    "9410170",  # San Diego, CA
    "9410230",  # La Jolla, CA
    "9410660",  # Los Angeles, CA
    "9410840",  # Santa Monica, CA
    "9411340",  # Santa Barbara, CA
    "9412110",  # Port San Luis, CA
    "9413450",  # Monterey, CA
    "9414290",  # San Francisco, CA
    "9414863",  # Richmond, CA
    "9415020",  # Point Reyes, CA
    "9416841",  # Arena Cove, CA
    "9418767",  # North Spit, CA
    "9419750",  # Crescent City, CA
    "9431647",  # Port Orford, OR
    "9432780",  # Charleston, OR
    "9435380",  # South Beach, OR
    "9437540",  # Garibaldi, OR
    "9439040",  # Astoria, OR
    "9440910",  # Toke Point, WA
    "9440569",  # Westport, WA
    "9446484",  # Tacoma, WA
    "9447130",  # Seattle, WA
    "9449880",  # Friday Harbor, WA
]

# Data products from CO-OPS
COOPS_PRODUCTS = {
    "water_level": {"product": "water_level", "datum": "MLLW", "units": "metric"},
    "predictions": {"product": "predictions", "datum": "MLLW", "units": "metric"},
    "currents": {"product": "currents", "units": "metric"},
    "water_temperature": {"product": "water_temperature", "units": "metric"},
    "air_temperature": {"product": "air_temperature", "units": "metric"},
    "wind": {"product": "wind", "units": "metric"},
    "air_pressure": {"product": "air_pressure", "units": "metric"},
    "salinity": {"product": "salinity"},
    "conductivity": {"product": "conductivity"},
    "visibility": {"product": "visibility", "units": "metric"},
}


class OceanicIngestion:
    """Handles oceanic data ingestion with medallion architecture"""

    def __init__(self, mode="incremental", hours_back=1, days_back=None):
        self.mode = mode
        self.hours_back = hours_back
        self.days_back = days_back
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "NOAA-Federated-Data-Lake/1.0 (contact@example.com)",
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

    def fetch_with_retry(
        self, url: str, params: Dict = None, max_retries: int = 3
    ) -> Optional[Dict]:
        """Fetch data from NOAA API with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                self.stats["apis_called"] += 1

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = 2**attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(
                        f"API returned {response.status_code}: {url} - {response.text[:200]}"
                    )
                    return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                else:
                    self.stats["errors"] += 1
                    return None
        return None

    def ingest_coops_data(
        self,
        station: str,
        product_name: str,
        product_config: Dict,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict]:
        """Ingest data from NOAA CO-OPS for a specific product"""
        records = []

        params = {
            "station": station,
            "product": product_config["product"],
            "begin_date": start_time.strftime("%Y%m%d %H:%M"),
            "end_date": end_time.strftime("%Y%m%d %H:%M"),
            "time_zone": "GMT",
            "application": "NOAA_Federated_Data_Lake",
            "format": "json",
        }

        # Add optional parameters
        if "datum" in product_config:
            params["datum"] = product_config["datum"]
        if "units" in product_config:
            params["units"] = product_config["units"]

        data = self.fetch_with_retry(COOPS_BASE_URL, params=params)
        if not data or "data" not in data:
            return records

        for observation in data["data"]:
            try:
                record = {
                    "record_id": hashlib.md5(
                        f"{station}_{product_name}_{observation.get('t')}".encode()
                    ).hexdigest(),
                    "station_id": station,
                    "product": product_name,
                    "timestamp": observation.get("t"),
                    "value": self.safe_float(observation.get("v")),
                    "quality": observation.get("q"),
                    "flags": observation.get("f"),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_COOPS",
                    "raw_json": json.dumps(observation),
                }

                # Add product-specific fields
                if product_name == "currents":
                    record["direction"] = self.safe_float(observation.get("d"))
                    record["speed"] = self.safe_float(observation.get("s"))
                    record["bin"] = observation.get("b")

                if product_name == "wind":
                    record["wind_speed"] = self.safe_float(observation.get("s"))
                    record["wind_direction"] = self.safe_float(observation.get("d"))
                    record["wind_gust"] = self.safe_float(observation.get("g"))

                records.append(record)
            except Exception as e:
                logger.error(f"Error processing {product_name} observation: {str(e)}")
                self.stats["errors"] += 1

        return records

    def ingest_station_metadata(self) -> List[Dict]:
        """Ingest station metadata from CO-OPS"""
        records = []

        # CO-OPS stations endpoint
        stations_url = (
            "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
        )

        data = self.fetch_with_retry(stations_url)
        if not data or "stations" not in data:
            return records

        for station in data["stations"]:
            try:
                record = {
                    "station_id": station.get("id"),
                    "name": station.get("name"),
                    "state": station.get("state"),
                    "latitude": self.safe_float(station.get("lat")),
                    "longitude": self.safe_float(station.get("lng")),
                    "timezone": station.get("timezone"),
                    "timezone_offset": station.get("timezoneOffset"),
                    "station_type": station.get("stationType"),
                    "products": json.dumps(station.get("products", [])),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_COOPS",
                    "raw_json": json.dumps(station),
                }
                records.append(record)
            except Exception as e:
                logger.error(f"Error processing station metadata: {str(e)}")
                self.stats["errors"] += 1

        return records

    def safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def write_bronze_layer(self, records: List[Dict], data_type: str):
        """Write raw data to Bronze layer (S3)"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}/hour={timestamp.hour:02d}"
        key = f"bronze/oceanic/{data_type}/{partition}/data_{self.ingestion_id}.json"

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

                # Validate and normalize
                if cleaned.get("timestamp"):
                    try:
                        # Ensure timestamp is ISO format
                        dt = datetime.fromisoformat(
                            cleaned["timestamp"].replace("Z", "+00:00")
                        )
                        cleaned["timestamp_parsed"] = dt.isoformat()
                        cleaned["hour"] = dt.hour
                        cleaned["day"] = dt.day
                        cleaned["month"] = dt.month
                        cleaned["year"] = dt.year
                    except Exception:
                        pass

                # Quality flags
                if cleaned.get("quality"):
                    cleaned["is_verified"] = cleaned["quality"] == "v"
                    cleaned["is_preliminary"] = cleaned["quality"] == "p"

                # Data availability
                cleaned["has_value"] = cleaned.get("value") is not None

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
        key = f"silver/oceanic/{data_type}/{partition}/data_{self.ingestion_id}.json"

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
        gold_records = []

        # Group by station and hour
        station_hour_groups = {}
        for record in silver_records:
            station = record.get("station_id")
            product = record.get("product")
            timestamp = record.get("timestamp", "")
            hour_key = f"{station}_{product}_{timestamp[:13]}"

            if hour_key not in station_hour_groups:
                station_hour_groups[hour_key] = []
            station_hour_groups[hour_key].append(record)

        # Create aggregated records
        for hour_key, group in station_hour_groups.items():
            try:
                values = [r["value"] for r in group if r.get("value") is not None]
                verified_count = len([r for r in group if r.get("is_verified")])

                gold_record = {
                    "station_id": group[0]["station_id"],
                    "product": group[0]["product"],
                    "hour": group[0]["timestamp"][:13],
                    "observation_count": len(group),
                    "avg_value": sum(values) / len(values) if values else None,
                    "max_value": max(values) if values else None,
                    "min_value": min(values) if values else None,
                    "verified_count": verified_count,
                    "data_quality_score": verified_count / len(group) if group else 0,
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                }

                # Product-specific aggregations
                if group[0].get("product") == "wind":
                    speeds = [r.get("wind_speed") for r in group if r.get("wind_speed")]
                    gusts = [r.get("wind_gust") for r in group if r.get("wind_gust")]
                    if speeds:
                        gold_record["avg_wind_speed"] = sum(speeds) / len(speeds)
                        gold_record["max_wind_speed"] = max(speeds)
                    if gusts:
                        gold_record["max_wind_gust"] = max(gusts)

                elif group[0].get("product") == "currents":
                    speeds = [r.get("speed") for r in group if r.get("speed")]
                    if speeds:
                        gold_record["avg_current_speed"] = sum(speeds) / len(speeds)
                        gold_record["max_current_speed"] = max(speeds)

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
        key = f"gold/oceanic/{data_type}/{partition}/data_{self.ingestion_id}.json"

        try:
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
        logger.info(f"Starting oceanic ingestion - Mode: {self.mode}")
        start_time = time.time()

        # Calculate time range
        end_dt = datetime.utcnow()
        if self.mode == "backfill" and self.days_back:
            start_dt = end_dt - timedelta(days=self.days_back)
        else:
            start_dt = end_dt - timedelta(hours=self.hours_back)

        logger.info(f"Time range: {start_dt} to {end_dt}")

        # 1. Ingest station metadata (once per run)
        logger.info("Ingesting station metadata...")
        stations = self.ingest_station_metadata()
        if stations:
            self.write_bronze_layer(stations, "stations")
            silver_stations = self.process_silver_layer(stations, "stations")
            self.write_silver_layer(silver_stations, "stations")
            self.write_gold_layer(silver_stations, "stations")

        # 2. Ingest data products for each station
        for i, station in enumerate(MAJOR_OCEAN_STATIONS):
            if i % 10 == 0:
                logger.info(
                    f"Processing station {i + 1}/{len(MAJOR_OCEAN_STATIONS)}: {station}"
                )

            for product_name, product_config in COOPS_PRODUCTS.items():
                try:
                    records = self.ingest_coops_data(
                        station, product_name, product_config, start_dt, end_dt
                    )

                    if records:
                        self.write_bronze_layer(records, product_name)
                        silver_records = self.process_silver_layer(
                            records, product_name
                        )
                        self.write_silver_layer(silver_records, product_name)
                        gold_records = self.process_gold_layer(
                            silver_records, product_name
                        )
                        self.write_gold_layer(gold_records, product_name)

                    # Rate limiting
                    time.sleep(0.3)

                except Exception as e:
                    logger.error(
                        f"Error processing station {station} product {product_name}: {str(e)}"
                    )
                    self.stats["errors"] += 1

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
        hours_back = event.get("hours_back", 1)
        days_back = event.get("days_back")

        logger.info(
            f"Lambda invoked - Mode: {mode}, Hours: {hours_back}, Days: {days_back}"
        )

        # Run ingestion
        ingestion = OceanicIngestion(
            mode=mode, hours_back=hours_back, days_back=days_back
        )
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
