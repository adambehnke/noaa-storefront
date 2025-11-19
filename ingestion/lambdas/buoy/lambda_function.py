"""
NOAA Buoy Data Ingestion Lambda
Implements Medallion Architecture: Bronze -> Silver -> Gold
Ingests current and historical buoy data from NOAA NDBC
"""

import hashlib
import json
import logging
import os
import re
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

# NOAA NDBC Configuration
NDBC_BASE_URL = "https://www.ndbc.noaa.gov"
NDBC_REALTIME_URL = f"{NDBC_BASE_URL}/data/realtime2"
NDBC_HISTORICAL_URL = f"{NDBC_BASE_URL}/data/historical/stdmet"

# Major US buoy stations for comprehensive coverage
MAJOR_BUOYS = [
    "44013",
    "44017",
    "44025",
    "44027",
    "44065",  # Northeast
    "41001",
    "41002",
    "41004",
    "41009",
    "41010",  # East Coast
    "42001",
    "42002",
    "42003",
    "42019",
    "42020",  # Gulf of Mexico
    "42036",
    "42039",
    "42040",
    "42056",
    "42057",  # Gulf of Mexico
    "46001",
    "46002",
    "46005",
    "46006",
    "46011",  # West Coast
    "46012",
    "46013",
    "46014",
    "46022",
    "46025",  # West Coast
    "46026",
    "46027",
    "46028",
    "46029",
    "46035",  # West Coast
    "46041",
    "46042",
    "46050",
    "46053",
    "46054",  # West Coast
    "46059",
    "46062",
    "46063",
    "46086",
    "46087",  # West Coast
    "51000",
    "51001",
    "51002",
    "51003",
    "51004",  # Hawaii
]


class BuoyIngestion:
    """Handles buoy data ingestion with medallion architecture"""

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

    def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch data from NOAA NDBC with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                self.stats["apis_called"] += 1

                if response.status_code == 200:
                    return response.text
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

    def parse_ndbc_standard_data(self, text: str, buoy_id: str) -> List[Dict]:
        """Parse NDBC standard meteorological data format"""
        records = []
        if not text:
            return records

        lines = text.strip().split("\n")
        if len(lines) < 3:
            return records

        # First line is column headers, second line is units
        headers = lines[0].split()
        units = lines[1].split()

        # Map headers (NDBC uses specific column names)
        header_map = {
            "#YY": "year",
            "YY": "year",
            "MM": "month",
            "DD": "day",
            "hh": "hour",
            "mm": "minute",
            "WDIR": "wind_direction",
            "WSPD": "wind_speed",
            "GST": "wind_gust",
            "WVHT": "wave_height",
            "DPD": "dominant_wave_period",
            "APD": "average_wave_period",
            "MWD": "mean_wave_direction",
            "PRES": "air_pressure",
            "ATMP": "air_temperature",
            "WTMP": "water_temperature",
            "DEWP": "dewpoint_temperature",
            "VIS": "visibility",
            "PTDY": "pressure_tendency",
            "TIDE": "tide",
        }

        # Parse data lines
        for line in lines[2:]:
            if not line.strip() or line.startswith("#"):
                continue

            try:
                values = line.split()
                if len(values) < len(headers):
                    continue

                record = {
                    "record_id": None,
                    "buoy_id": buoy_id,
                    "timestamp": None,
                }

                # Parse values
                for i, header in enumerate(headers):
                    if i >= len(values):
                        break

                    field_name = header_map.get(header, header.lower())
                    value = values[i]

                    # Convert 'MM' (missing) to None
                    if value in ["MM", "999", "9999", "999.0", "99.0"]:
                        record[field_name] = None
                    else:
                        try:
                            record[field_name] = float(value)
                        except ValueError:
                            record[field_name] = value

                # Create timestamp
                if all(k in record for k in ["year", "month", "day", "hour", "minute"]):
                    year = int(record["year"])
                    if year < 100:
                        year += 2000 if year < 50 else 1900

                    timestamp = datetime(
                        year,
                        int(record["month"]),
                        int(record["day"]),
                        int(record["hour"]),
                        int(record["minute"]),
                    )
                    record["timestamp"] = timestamp.isoformat() + "Z"
                    record["record_id"] = hashlib.md5(
                        f"{buoy_id}_{record['timestamp']}".encode()
                    ).hexdigest()

                # Add metadata
                record["ingestion_timestamp"] = datetime.utcnow().isoformat()
                record["ingestion_id"] = self.ingestion_id
                record["data_source"] = "NOAA_NDBC"

                if record.get("timestamp") and record.get("record_id"):
                    records.append(record)

            except Exception as e:
                logger.error(f"Error parsing buoy line: {str(e)}")
                self.stats["errors"] += 1
                continue

        return records

    def ingest_realtime_buoy_data(self, buoy_id: str) -> List[Dict]:
        """Ingest real-time buoy data"""
        records = []

        # Standard meteorological data
        url = f"{NDBC_REALTIME_URL}/{buoy_id}.txt"
        text = self.fetch_with_retry(url)

        if text:
            records.extend(self.parse_ndbc_standard_data(text, buoy_id))

        # Spectral wave data
        spec_url = f"{NDBC_REALTIME_URL}/{buoy_id}.spec"
        spec_text = self.fetch_with_retry(spec_url)
        if spec_text:
            spec_records = self.parse_spectral_data(spec_text, buoy_id)
            records.extend(spec_records)

        return records

    def parse_spectral_data(self, text: str, buoy_id: str) -> List[Dict]:
        """Parse spectral wave data"""
        records = []
        # Simplified - spectral data is complex, storing as summary
        if not text:
            return records

        lines = text.strip().split("\n")
        for line in lines:
            if line.startswith("(") or not line.strip():
                continue

            try:
                parts = line.split()
                if len(parts) >= 5:
                    record = {
                        "record_id": hashlib.md5(
                            f"{buoy_id}_spectral_{parts[0]}".encode()
                        ).hexdigest(),
                        "buoy_id": buoy_id,
                        "data_type": "spectral",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "frequency": self.safe_float(parts[0]),
                        "spectral_density": self.safe_float(parts[1])
                        if len(parts) > 1
                        else None,
                        "ingestion_timestamp": datetime.utcnow().isoformat(),
                        "ingestion_id": self.ingestion_id,
                        "data_source": "NOAA_NDBC",
                    }
                    records.append(record)
            except Exception as e:
                logger.error(f"Error parsing spectral data: {str(e)}")
                continue

        return records

    def ingest_buoy_metadata(self) -> List[Dict]:
        """Ingest buoy station metadata"""
        records = []

        # NDBC stations XML endpoint
        url = f"{NDBC_BASE_URL}/activestations.xml"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return records

            # Parse XML (simplified - would use xml.etree in production)
            text = response.text

            # Extract station info using regex (simplified)
            station_pattern = r'<station id="([^"]+)".*?lat="([^"]+)".*?lon="([^"]+)".*?name="([^"]+)"'
            matches = re.findall(station_pattern, text, re.DOTALL)

            for match in matches:
                station_id, lat, lon, name = match
                record = {
                    "buoy_id": station_id,
                    "name": name,
                    "latitude": self.safe_float(lat),
                    "longitude": self.safe_float(lon),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_NDBC",
                }
                records.append(record)

        except Exception as e:
            logger.error(f"Error ingesting buoy metadata: {str(e)}")
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
        key = f"bronze/buoy/{data_type}/{partition}/data_{self.ingestion_id}.json"

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
                # Create cleaned record
                cleaned = {k: v for k, v in record.items() if k != "raw_json"}

                # Validate numeric ranges
                if cleaned.get("wave_height") is not None:
                    if cleaned["wave_height"] < 0 or cleaned["wave_height"] > 30:
                        cleaned["wave_height_valid"] = False
                    else:
                        cleaned["wave_height_valid"] = True

                if cleaned.get("water_temperature") is not None:
                    if (
                        cleaned["water_temperature"] < -5
                        or cleaned["water_temperature"] > 40
                    ):
                        cleaned["water_temperature_valid"] = False
                    else:
                        cleaned["water_temperature_valid"] = True

                # Calculate data completeness
                data_fields = [
                    "wind_speed",
                    "wave_height",
                    "water_temperature",
                    "air_temperature",
                ]
                available_fields = sum(
                    1 for field in data_fields if cleaned.get(field) is not None
                )
                cleaned["data_completeness"] = available_fields / len(data_fields)

                # Add quality indicators
                cleaned["has_wave_data"] = cleaned.get("wave_height") is not None
                cleaned["has_wind_data"] = cleaned.get("wind_speed") is not None
                cleaned["has_temperature_data"] = (
                    cleaned.get("water_temperature") is not None
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
        key = f"silver/buoy/{data_type}/{partition}/data_{self.ingestion_id}.json"

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

        # Group by buoy and hour
        buoy_hour_groups = {}
        for record in silver_records:
            buoy = record.get("buoy_id")
            timestamp = record.get("timestamp", "")
            hour_key = f"{buoy}_{timestamp[:13]}"

            if hour_key not in buoy_hour_groups:
                buoy_hour_groups[hour_key] = []
            buoy_hour_groups[hour_key].append(record)

        # Create aggregated records
        for hour_key, group in buoy_hour_groups.items():
            try:
                # Aggregate wave data
                wave_heights = [r["wave_height"] for r in group if r.get("wave_height")]
                wave_periods = [
                    r["dominant_wave_period"]
                    for r in group
                    if r.get("dominant_wave_period")
                ]

                # Aggregate wind data
                wind_speeds = [r["wind_speed"] for r in group if r.get("wind_speed")]
                wind_gusts = [r["wind_gust"] for r in group if r.get("wind_gust")]

                # Aggregate temperature data
                water_temps = [
                    r["water_temperature"] for r in group if r.get("water_temperature")
                ]
                air_temps = [
                    r["air_temperature"] for r in group if r.get("air_temperature")
                ]

                gold_record = {
                    "buoy_id": group[0]["buoy_id"],
                    "hour": group[0]["timestamp"][:13],
                    "observation_count": len(group),
                    # Wave statistics
                    "avg_wave_height": sum(wave_heights) / len(wave_heights)
                    if wave_heights
                    else None,
                    "max_wave_height": max(wave_heights) if wave_heights else None,
                    "min_wave_height": min(wave_heights) if wave_heights else None,
                    "avg_wave_period": sum(wave_periods) / len(wave_periods)
                    if wave_periods
                    else None,
                    # Wind statistics
                    "avg_wind_speed": sum(wind_speeds) / len(wind_speeds)
                    if wind_speeds
                    else None,
                    "max_wind_speed": max(wind_speeds) if wind_speeds else None,
                    "max_wind_gust": max(wind_gusts) if wind_gusts else None,
                    # Temperature statistics
                    "avg_water_temperature": sum(water_temps) / len(water_temps)
                    if water_temps
                    else None,
                    "avg_air_temperature": sum(air_temps) / len(air_temps)
                    if air_temps
                    else None,
                    # Data quality
                    "data_completeness": sum(
                        r.get("data_completeness", 0) for r in group
                    )
                    / len(group),
                    "wave_data_available": any(r.get("has_wave_data") for r in group),
                    "wind_data_available": any(r.get("has_wind_data") for r in group),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                }

                # Calculate sea state
                if gold_record.get("avg_wave_height"):
                    gold_record["sea_state"] = self.calculate_sea_state(
                        gold_record["avg_wave_height"]
                    )

                gold_records.append(gold_record)

            except Exception as e:
                logger.error(f"Error processing Gold record: {str(e)}")
                self.stats["errors"] += 1

        return gold_records

    def calculate_sea_state(self, wave_height: float) -> str:
        """Calculate sea state based on wave height (WMO scale)"""
        if wave_height < 0.1:
            return "calm"
        elif wave_height < 0.5:
            return "smooth"
        elif wave_height < 1.25:
            return "slight"
        elif wave_height < 2.5:
            return "moderate"
        elif wave_height < 4.0:
            return "rough"
        elif wave_height < 6.0:
            return "very_rough"
        elif wave_height < 9.0:
            return "high"
        elif wave_height < 14.0:
            return "very_high"
        else:
            return "phenomenal"

    def write_gold_layer(self, records: List[Dict], data_type: str):
        """Write aggregated data to Gold layer (queryable via Athena)"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = (
            f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}"
        )
        key = f"gold/buoy/{data_type}/{partition}/data_{self.ingestion_id}.json"

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
        logger.info(f"Starting buoy ingestion - Mode: {self.mode}")
        start_time = time.time()

        # 1. Ingest buoy metadata (once per run)
        logger.info("Ingesting buoy metadata...")
        metadata = self.ingest_buoy_metadata()
        if metadata:
            self.write_bronze_layer(metadata, "metadata")
            silver_metadata = self.process_silver_layer(metadata, "metadata")
            self.write_silver_layer(silver_metadata, "metadata")
            self.write_gold_layer(silver_metadata, "metadata")

        # 2. Ingest real-time buoy observations
        logger.info(f"Ingesting observations for {len(MAJOR_BUOYS)} buoys...")
        all_observations = []

        for i, buoy in enumerate(MAJOR_BUOYS):
            if i % 10 == 0:
                logger.info(f"Processing buoy {i + 1}/{len(MAJOR_BUOYS)}: {buoy}")

            observations = self.ingest_realtime_buoy_data(buoy)
            if observations:
                all_observations.extend(observations)

            # Rate limiting
            if i < len(MAJOR_BUOYS) - 1:
                time.sleep(0.5)

        # Write observations through medallion layers
        if all_observations:
            self.write_bronze_layer(all_observations, "observations")
            silver_obs = self.process_silver_layer(all_observations, "observations")
            self.write_silver_layer(silver_obs, "observations")
            gold_obs = self.process_gold_layer(silver_obs, "observations")
            self.write_gold_layer(gold_obs, "observations")

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
        ingestion = BuoyIngestion(mode=mode, hours_back=hours_back, days_back=days_back)
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
