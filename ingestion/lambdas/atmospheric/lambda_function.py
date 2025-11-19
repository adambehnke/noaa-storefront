"""
NOAA Atmospheric Data Ingestion Lambda
Implements Medallion Architecture: Bronze -> Silver -> Gold
Ingests current and historical atmospheric data from NOAA APIs
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
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

# NOAA API Configuration
NOAA_ENDPOINTS = {
    "observations": "https://api.weather.gov/stations/{station}/observations",
    "forecasts": "https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast",
    "alerts": "https://api.weather.gov/alerts/active",
    "stations": "https://api.weather.gov/stations",
    "radar": "https://api.weather.gov/radar/stations/{station}",
    "products": "https://api.weather.gov/products/types/{type}/locations/{location}",
}

# Major US weather stations for comprehensive coverage
MAJOR_STATIONS = [
    "KBOS",
    "KJFK",
    "KPHL",
    "KDCA",
    "KATL",
    "KMIA",
    "KORD",
    "KDFW",
    "KDEN",
    "KPHX",
    "KLAX",
    "KSFO",
    "KSEA",
    "KPDX",
    "KLAS",
    "KSLC",
    "KMSP",
    "KDTW",
    "KCLT",
    "KMCO",
    "KBNA",
    "KSTL",
    "KCLE",
    "KPIT",
    "KHOU",
    "KIAH",
    "KAUS",
    "KSAT",
    "KOKC",
    "KMCI",
    "KBWI",
    "KRDU",
    "KRIC",
    "KORF",
    "KGSO",
    "KCHS",
    "KSAV",
    "KJAX",
    "KTPA",
    "KPBI",
    "KFLL",
    "KMSY",
    "KBTR",
    "KLIT",
    "KMEM",
    "KBHM",
    "KCRW",
    "KTYS",
    "KLEX",
    "KCVG",
    "KCMH",
    "KIND",
    "KMDW",
    "KMKE",
    "KGRR",
    "KDSM",
    "KOMX",
    "KOMA",
    "KFSD",
    "KBIS",
    "KFAR",
    "KRAP",
    "KGEG",
    "KBOI",
]


class AtmosphericIngestion:
    """Handles atmospheric data ingestion with medallion architecture"""

    def __init__(self, mode="incremental", hours_back=1, days_back=None):
        self.mode = mode
        self.hours_back = hours_back
        self.days_back = days_back
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
                    # Rate limited - wait and retry
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

    def ingest_observations(self, station: str, start_time: datetime) -> List[Dict]:
        """Ingest observation data for a station"""
        records = []
        url = NOAA_ENDPOINTS["observations"].format(station=station)
        url += f"?start={start_time.isoformat()}Z"

        data = self.fetch_with_retry(url)
        if not data or "features" not in data:
            return records

        for feature in data["features"]:
            try:
                props = feature.get("properties", {})
                record = {
                    "record_id": hashlib.md5(
                        f"{station}_{props.get('timestamp')}".encode()
                    ).hexdigest(),
                    "station_id": station,
                    "timestamp": props.get("timestamp"),
                    "temperature": self.extract_value(props.get("temperature")),
                    "dewpoint": self.extract_value(props.get("dewpoint")),
                    "wind_direction": self.extract_value(props.get("windDirection")),
                    "wind_speed": self.extract_value(props.get("windSpeed")),
                    "wind_gust": self.extract_value(props.get("windGust")),
                    "barometric_pressure": self.extract_value(
                        props.get("barometricPressure")
                    ),
                    "sea_level_pressure": self.extract_value(
                        props.get("seaLevelPressure")
                    ),
                    "visibility": self.extract_value(props.get("visibility")),
                    "max_temperature_24h": self.extract_value(
                        props.get("maxTemperatureLast24Hours")
                    ),
                    "min_temperature_24h": self.extract_value(
                        props.get("minTemperatureLast24Hours")
                    ),
                    "precipitation_last_hour": self.extract_value(
                        props.get("precipitationLastHour")
                    ),
                    "precipitation_last_3h": self.extract_value(
                        props.get("precipitationLast3Hours")
                    ),
                    "precipitation_last_6h": self.extract_value(
                        props.get("precipitationLast6Hours")
                    ),
                    "relative_humidity": self.extract_value(
                        props.get("relativeHumidity")
                    ),
                    "wind_chill": self.extract_value(props.get("windChill")),
                    "heat_index": self.extract_value(props.get("heatIndex")),
                    "cloud_layers": json.dumps(props.get("cloudLayers", [])),
                    "present_weather": json.dumps(props.get("presentWeather", [])),
                    "raw_message": props.get("rawMessage", ""),
                    "text_description": props.get("textDescription", ""),
                    "elevation": self.extract_value(props.get("elevation")),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_Weather_API",
                    "raw_json": json.dumps(feature),
                }
                records.append(record)
            except Exception as e:
                logger.error(f"Error processing observation: {str(e)}")
                self.stats["errors"] += 1

        return records

    def ingest_alerts(self) -> List[Dict]:
        """Ingest active weather alerts"""
        records = []
        url = NOAA_ENDPOINTS["alerts"]

        data = self.fetch_with_retry(url)
        if not data or "features" not in data:
            return records

        for feature in data["features"]:
            try:
                props = feature.get("properties", {})
                geom = feature.get("geometry")

                record = {
                    "alert_id": props.get(
                        "id", hashlib.md5(str(props).encode()).hexdigest()
                    ),
                    "event": props.get("event"),
                    "headline": props.get("headline"),
                    "description": props.get("description"),
                    "instruction": props.get("instruction"),
                    "severity": props.get("severity"),
                    "certainty": props.get("certainty"),
                    "urgency": props.get("urgency"),
                    "status": props.get("status"),
                    "message_type": props.get("messageType"),
                    "category": props.get("category"),
                    "sender": props.get("sender"),
                    "sender_name": props.get("senderName"),
                    "sent": props.get("sent"),
                    "effective": props.get("effective"),
                    "onset": props.get("onset"),
                    "expires": props.get("expires"),
                    "ends": props.get("ends"),
                    "response": props.get("response"),
                    "affected_zones": json.dumps(props.get("affectedZones", [])),
                    "references": json.dumps(props.get("references", [])),
                    "parameters": json.dumps(props.get("parameters", {})),
                    "geometry": json.dumps(geom) if geom else None,
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_Weather_API",
                    "raw_json": json.dumps(feature),
                }
                records.append(record)
            except Exception as e:
                logger.error(f"Error processing alert: {str(e)}")
                self.stats["errors"] += 1

        return records

    def ingest_stations(self) -> List[Dict]:
        """Ingest station metadata"""
        records = []
        url = NOAA_ENDPOINTS["stations"]

        data = self.fetch_with_retry(url)
        if not data or "features" not in data:
            return records

        for feature in data["features"]:
            try:
                props = feature.get("properties", {})
                geom = feature.get("geometry", {})
                coords = geom.get("coordinates", [None, None])

                record = {
                    "station_id": props.get("stationIdentifier"),
                    "name": props.get("name"),
                    "timezone": props.get("timeZone"),
                    "forecast_office": props.get("forecast"),
                    "county": props.get("county"),
                    "fire_weather_zone": props.get("fireWeatherZone"),
                    "latitude": coords[1] if len(coords) > 1 else None,
                    "longitude": coords[0] if len(coords) > 0 else None,
                    "elevation_value": self.extract_value(props.get("elevation")),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_Weather_API",
                    "raw_json": json.dumps(feature),
                }
                records.append(record)
            except Exception as e:
                logger.error(f"Error processing station: {str(e)}")
                self.stats["errors"] += 1

        return records

    def extract_value(self, obj: Optional[Dict]) -> Optional[float]:
        """Extract numeric value from NOAA value object"""
        if obj and isinstance(obj, dict):
            value = obj.get("value")
            if value is not None:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
        return None

    def write_bronze_layer(self, records: List[Dict], data_type: str):
        """Write raw data to Bronze layer (S3)"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}/hour={timestamp.hour:02d}"
        key = (
            f"bronze/atmospheric/{data_type}/{partition}/data_{self.ingestion_id}.json"
        )

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
                if data_type == "observations":
                    if cleaned.get("timestamp"):
                        cleaned["observation_time"] = cleaned["timestamp"]
                    cleaned["has_temperature"] = cleaned.get("temperature") is not None
                    cleaned["has_precipitation"] = any(
                        [
                            cleaned.get("precipitation_last_hour"),
                            cleaned.get("precipitation_last_3h"),
                            cleaned.get("precipitation_last_6h"),
                        ]
                    )

                elif data_type == "alerts":
                    if cleaned.get("severity"):
                        cleaned["severity_priority"] = {
                            "Extreme": 4,
                            "Severe": 3,
                            "Moderate": 2,
                            "Minor": 1,
                        }.get(cleaned["severity"], 0)
                    cleaned["is_active"] = cleaned.get("status") == "Actual"

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
        key = (
            f"silver/atmospheric/{data_type}/{partition}/data_{self.ingestion_id}.json"
        )

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

        if data_type == "observations":
            # Group by station and hour
            station_groups = {}
            for record in silver_records:
                station = record.get("station_id")
                timestamp = record.get("timestamp", "")
                hour_key = f"{station}_{timestamp[:13]}"  # Up to hour

                if hour_key not in station_groups:
                    station_groups[hour_key] = []
                station_groups[hour_key].append(record)

            # Create aggregated records
            for hour_key, group in station_groups.items():
                temps = [r["temperature"] for r in group if r.get("temperature")]
                winds = [r["wind_speed"] for r in group if r.get("wind_speed")]

                gold_record = {
                    "station_id": group[0]["station_id"],
                    "hour": group[0]["timestamp"][:13],
                    "observation_count": len(group),
                    "avg_temperature": sum(temps) / len(temps) if temps else None,
                    "max_temperature": max(temps) if temps else None,
                    "min_temperature": min(temps) if temps else None,
                    "avg_wind_speed": sum(winds) / len(winds) if winds else None,
                    "max_wind_speed": max(winds) if winds else None,
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "data_quality_score": len(
                        [r for r in group if r.get("has_temperature")]
                    )
                    / len(group),
                }
                gold_records.append(gold_record)

        elif data_type == "alerts":
            # Enrich alerts with priority and geographic info
            for record in silver_records:
                gold_record = record.copy()
                gold_record["alert_priority"] = self.calculate_alert_priority(record)
                gold_records.append(gold_record)

        return gold_records

    def write_gold_layer(self, records: List[Dict], data_type: str):
        """Write aggregated data to Gold layer (queryable via Athena)"""
        if not records:
            return

        timestamp = datetime.utcnow()
        partition = (
            f"year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}"
        )
        key = f"gold/atmospheric/{data_type}/{partition}/data_{self.ingestion_id}.json"

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

    def calculate_alert_priority(self, alert: Dict) -> int:
        """Calculate numeric priority for an alert"""
        priority = 0
        priority += alert.get("severity_priority", 0) * 10
        if alert.get("urgency") == "Immediate":
            priority += 5
        if alert.get("certainty") in ["Observed", "Likely"]:
            priority += 3
        return priority

    def run_ingestion(self):
        """Main ingestion workflow"""
        logger.info(f"Starting atmospheric ingestion - Mode: {self.mode}")
        start_time = time.time()

        # Calculate time range
        if self.mode == "backfill" and self.days_back:
            start_dt = datetime.utcnow() - timedelta(days=self.days_back)
        else:
            start_dt = datetime.utcnow() - timedelta(hours=self.hours_back)

        # 1. Ingest station metadata (once per run)
        logger.info("Ingesting station metadata...")
        stations = self.ingest_stations()
        if stations:
            self.write_bronze_layer(stations, "stations")
            silver_stations = self.process_silver_layer(stations, "stations")
            self.write_silver_layer(silver_stations, "stations")
            self.write_gold_layer(silver_stations, "stations")

        # 2. Ingest active alerts
        logger.info("Ingesting weather alerts...")
        alerts = self.ingest_alerts()
        if alerts:
            self.write_bronze_layer(alerts, "alerts")
            silver_alerts = self.process_silver_layer(alerts, "alerts")
            self.write_silver_layer(silver_alerts, "alerts")
            gold_alerts = self.process_gold_layer(silver_alerts, "alerts")
            self.write_gold_layer(gold_alerts, "alerts")

        # 3. Ingest observations for major stations
        logger.info(f"Ingesting observations for {len(MAJOR_STATIONS)} stations...")
        all_observations = []

        for i, station in enumerate(MAJOR_STATIONS):
            if i % 10 == 0:
                logger.info(
                    f"Processing station {i + 1}/{len(MAJOR_STATIONS)}: {station}"
                )

            observations = self.ingest_observations(station, start_dt)
            if observations:
                all_observations.extend(observations)

            # Rate limiting - be respectful to NOAA API
            if i < len(MAJOR_STATIONS) - 1:
                time.sleep(0.5)

        # Write observations
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
        ingestion = AtmosphericIngestion(
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
