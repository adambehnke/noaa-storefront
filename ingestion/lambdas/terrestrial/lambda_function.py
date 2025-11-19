"""
NOAA Terrestrial Data Ingestion Lambda
Implements Medallion Architecture: Bronze -> Silver -> Gold
Ingests land-based environmental data from NOAA sources
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

# NOAA Weather API
NOAA_WEATHER_API = "https://api.weather.gov"

# Major inland/terrestrial weather stations (non-coastal)
MAJOR_TERRESTRIAL_STATIONS = [
    "KORD",  # Chicago O'Hare
    "KATL",  # Atlanta Hartsfield
    "KDFW",  # Dallas/Fort Worth
    "KDEN",  # Denver International
    "KPHX",  # Phoenix Sky Harbor
    "KLAS",  # Las Vegas McCarran
    "KMSP",  # Minneapolis-St. Paul
    "KDTW",  # Detroit Metro
    "KSTL",  # St. Louis Lambert
    "KCLE",  # Cleveland Hopkins
    "KPIT",  # Pittsburgh International
    "KCVG",  # Cincinnati/Northern Kentucky
    "KCMH",  # Columbus, OH
    "KIND",  # Indianapolis International
    "KMCI",  # Kansas City International
    "KOKC",  # Oklahoma City Will Rogers
    "KAUS",  # Austin-Bergstrom
    "KSAT",  # San Antonio International
    "KSLC",  # Salt Lake City International
    "KABQ",  # Albuquerque International
    "KTUS",  # Tucson International
    "KBOI",  # Boise Air Terminal
    "KGEG",  # Spokane International
    "KFAR",  # Fargo Hector
    "KBIS",  # Bismarck Municipal
    "KRAP",  # Rapid City Regional
    "KDSM",  # Des Moines International
    "KOMX",  # Omaha Eppley
    "KLIT",  # Little Rock National
    "KMEM",  # Memphis International
    "KBNA",  # Nashville International
    "KBHM",  # Birmingham-Shuttlesworth
    "KLEX",  # Lexington Blue Grass
    "KTYS",  # Knoxville McGhee Tyson
]

# Terrestrial data categories
TERRESTRIAL_CATEGORIES = [
    "temperature",
    "precipitation",
    "wind",
    "soil_moisture",
    "vegetation",
    "drought",
    "air_quality",
    "fire_weather",
]


class TerrestrialIngestion:
    """Handles terrestrial data ingestion with medallion architecture"""

    def __init__(self, mode="incremental", hours_back=1):
        self.mode = mode
        self.hours_back = hours_back
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

    def ingest_station_observations(self, station: str) -> List[Dict]:
        """Ingest terrestrial weather observations from a station"""
        records = []

        try:
            # Get latest observations
            url = f"{NOAA_WEATHER_API}/stations/{station}/observations/latest"
            data = self.fetch_with_retry(url)

            if not data or "properties" not in data:
                return records

            props = data["properties"]
            geom = data.get("geometry")

            # Extract terrestrial-specific metrics
            record = {
                "record_id": hashlib.md5(
                    f"{station}_{props.get('timestamp')}".encode()
                ).hexdigest(),
                "station_id": station,
                "timestamp": props.get("timestamp"),
                # Temperature data
                "temperature": self.extract_value(props.get("temperature")),
                "dewpoint": self.extract_value(props.get("dewpoint")),
                "heat_index": self.extract_value(props.get("heatIndex")),
                "wind_chill": self.extract_value(props.get("windChill")),
                # Atmospheric data
                "relative_humidity": self.extract_value(props.get("relativeHumidity")),
                "barometric_pressure": self.extract_value(
                    props.get("barometricPressure")
                ),
                # Precipitation data
                "precipitation_last_hour": self.extract_value(
                    props.get("precipitationLastHour")
                ),
                "precipitation_last_3h": self.extract_value(
                    props.get("precipitationLast3Hours")
                ),
                "precipitation_last_6h": self.extract_value(
                    props.get("precipitationLast6Hours")
                ),
                # Wind data
                "wind_direction": self.extract_value(props.get("windDirection")),
                "wind_speed": self.extract_value(props.get("windSpeed")),
                "wind_gust": self.extract_value(props.get("windGust")),
                # Visibility
                "visibility": self.extract_value(props.get("visibility")),
                # Cloud cover
                "cloud_layers": json.dumps(props.get("cloudLayers", [])),
                # Weather conditions
                "present_weather": json.dumps(props.get("presentWeather", [])),
                "text_description": props.get("textDescription", ""),
                # Location
                "elevation": self.extract_value(props.get("elevation")),
                "geometry": json.dumps(geom) if geom else None,
                # Metadata
                "ingestion_timestamp": datetime.utcnow().isoformat(),
                "ingestion_id": self.ingestion_id,
                "data_source": "NOAA_Weather_API",
                "raw_json": json.dumps(data),
            }
            records.append(record)

        except Exception as e:
            logger.error(
                f"Error ingesting observations for station {station}: {str(e)}"
            )
            self.stats["errors"] += 1

        return records

    def ingest_drought_data(self) -> List[Dict]:
        """Ingest drought monitoring data (placeholder - requires NDMC integration)"""
        records = []

        # Note: This would integrate with US Drought Monitor or NOAA's drought indices
        # For now, returning empty as it requires additional API setup
        logger.info("Drought data ingestion not yet implemented (requires NDMC API)")

        return records

    def ingest_fire_weather(self) -> List[Dict]:
        """Ingest fire weather alerts and indices"""
        records = []

        try:
            # Get fire weather zone alerts
            url = f"{NOAA_WEATHER_API}/alerts/active?zone_type=fire"
            data = self.fetch_with_retry(url)

            if not data or "features" not in data:
                return records

            for feature in data["features"]:
                try:
                    props = feature.get("properties", {})
                    geom = feature.get("geometry")

                    record = {
                        "record_id": hashlib.md5(
                            f"fire_{props.get('id')}".encode()
                        ).hexdigest(),
                        "alert_id": props.get("id"),
                        "alert_type": "fire_weather",
                        "event": props.get("event"),
                        "headline": props.get("headline"),
                        "description": props.get("description"),
                        "instruction": props.get("instruction"),
                        "severity": props.get("severity"),
                        "urgency": props.get("urgency"),
                        "certainty": props.get("certainty"),
                        "area_desc": props.get("areaDesc"),
                        "sent": props.get("sent"),
                        "effective": props.get("effective"),
                        "onset": props.get("onset"),
                        "expires": props.get("expires"),
                        "affected_zones": json.dumps(props.get("affectedZones", [])),
                        "geometry": json.dumps(geom) if geom else None,
                        "ingestion_timestamp": datetime.utcnow().isoformat(),
                        "ingestion_id": self.ingestion_id,
                        "data_source": "NOAA_Weather_API",
                        "raw_json": json.dumps(feature),
                    }
                    records.append(record)
                except Exception as e:
                    logger.error(f"Error processing fire weather alert: {str(e)}")
                    self.stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error ingesting fire weather data: {str(e)}")
            self.stats["errors"] += 1

        return records

    def ingest_soil_moisture_data(self) -> List[Dict]:
        """Ingest soil moisture data (placeholder - requires SCAN/SNOTEL integration)"""
        records = []

        # Note: This would integrate with USDA SCAN (Soil Climate Analysis Network)
        # or NRCS SNOTEL data, which NOAA often references
        logger.info(
            "Soil moisture data ingestion not yet implemented (requires SCAN/SNOTEL API)"
        )

        return records

    def ingest_station_metadata(self) -> List[Dict]:
        """Ingest terrestrial station metadata"""
        records = []

        for station_id in MAJOR_TERRESTRIAL_STATIONS:
            try:
                url = f"{NOAA_WEATHER_API}/stations/{station_id}"
                data = self.fetch_with_retry(url)

                if not data or "properties" not in data:
                    continue

                props = data["properties"]
                geom = data.get("geometry", {})
                coords = geom.get("coordinates", [None, None])

                record = {
                    "station_id": station_id,
                    "name": props.get("name"),
                    "timezone": props.get("timeZone"),
                    "forecast_office": props.get("forecast"),
                    "county": props.get("county"),
                    "fire_weather_zone": props.get("fireWeatherZone"),
                    "latitude": coords[1] if len(coords) > 1 else None,
                    "longitude": coords[0] if len(coords) > 0 else None,
                    "elevation": self.extract_value(props.get("elevation")),
                    "station_type": "terrestrial",
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                    "ingestion_id": self.ingestion_id,
                    "data_source": "NOAA_Weather_API",
                    "raw_json": json.dumps(data),
                }
                records.append(record)

                # Rate limiting
                time.sleep(0.3)

            except Exception as e:
                logger.error(
                    f"Error ingesting metadata for station {station_id}: {str(e)}"
                )
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
            f"bronze/terrestrial/{data_type}/{partition}/data_{self.ingestion_id}.json"
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

                # Validate timestamp
                if cleaned.get("timestamp"):
                    try:
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

                # Calculate derived terrestrial metrics
                temp = cleaned.get("temperature")
                humidity = cleaned.get("relative_humidity")

                # Heat stress indicators
                if temp is not None and temp > 30:
                    cleaned["high_temperature_alert"] = True
                else:
                    cleaned["high_temperature_alert"] = False

                # Cold stress indicators
                if temp is not None and temp < 0:
                    cleaned["freezing_conditions"] = True
                else:
                    cleaned["freezing_conditions"] = False

                # Precipitation indicators
                precip_1h = cleaned.get("precipitation_last_hour")
                precip_3h = cleaned.get("precipitation_last_3h")
                precip_6h = cleaned.get("precipitation_last_6h")

                cleaned["has_precipitation"] = any(
                    [
                        precip_1h and precip_1h > 0,
                        precip_3h and precip_3h > 0,
                        precip_6h and precip_6h > 0,
                    ]
                )

                # Heavy precipitation alert (>25mm in 3 hours)
                if precip_3h and precip_3h > 25:
                    cleaned["heavy_precipitation_alert"] = True
                else:
                    cleaned["heavy_precipitation_alert"] = False

                # Wind indicators
                wind_speed = cleaned.get("wind_speed")
                if wind_speed is not None:
                    if wind_speed > 15:  # > 15 m/s
                        cleaned["strong_winds"] = True
                    else:
                        cleaned["strong_winds"] = False

                # Data quality indicators
                cleaned["has_temperature"] = temp is not None
                cleaned["has_precipitation_data"] = any(
                    [
                        precip_1h is not None,
                        precip_3h is not None,
                        precip_6h is not None,
                    ]
                )
                cleaned["has_wind_data"] = wind_speed is not None
                cleaned["has_humidity_data"] = humidity is not None

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
            f"silver/terrestrial/{data_type}/{partition}/data_{self.ingestion_id}.json"
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

        # Group by station and hour
        station_hour_groups = {}
        for record in silver_records:
            station = record.get("station_id")
            timestamp = record.get("timestamp", "")
            hour_key = f"{station}_{timestamp[:13]}"

            if hour_key not in station_hour_groups:
                station_hour_groups[hour_key] = []
            station_hour_groups[hour_key].append(record)

        # Create aggregated records
        for hour_key, group in station_hour_groups.items():
            try:
                # Aggregate temperature
                temps = [r["temperature"] for r in group if r.get("temperature")]
                # Aggregate humidity
                humidities = [
                    r["relative_humidity"] for r in group if r.get("relative_humidity")
                ]
                # Aggregate precipitation
                precips = [
                    r["precipitation_last_hour"]
                    for r in group
                    if r.get("precipitation_last_hour")
                ]
                # Aggregate wind
                winds = [r["wind_speed"] for r in group if r.get("wind_speed")]

                gold_record = {
                    "station_id": group[0]["station_id"],
                    "hour": group[0]["timestamp"][:13],
                    "observation_count": len(group),
                    # Temperature statistics
                    "avg_temperature": sum(temps) / len(temps) if temps else None,
                    "max_temperature": max(temps) if temps else None,
                    "min_temperature": min(temps) if temps else None,
                    "temperature_range": (max(temps) - min(temps)) if temps else None,
                    # Humidity statistics
                    "avg_humidity": sum(humidities) / len(humidities)
                    if humidities
                    else None,
                    # Precipitation statistics
                    "total_precipitation": sum(precips) if precips else None,
                    "max_precipitation_rate": max(precips) if precips else None,
                    # Wind statistics
                    "avg_wind_speed": sum(winds) / len(winds) if winds else None,
                    "max_wind_speed": max(winds) if winds else None,
                    # Alert counts
                    "high_temp_events": len(
                        [r for r in group if r.get("high_temperature_alert")]
                    ),
                    "freezing_events": len(
                        [r for r in group if r.get("freezing_conditions")]
                    ),
                    "heavy_precip_events": len(
                        [r for r in group if r.get("heavy_precipitation_alert")]
                    ),
                    "strong_wind_events": len(
                        [r for r in group if r.get("strong_winds")]
                    ),
                    # Data quality
                    "data_completeness": len(
                        [r for r in group if r.get("has_temperature")]
                    )
                    / len(group),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                }

                # Calculate comfort index (simplified)
                if gold_record.get("avg_temperature") and gold_record.get(
                    "avg_humidity"
                ):
                    temp = gold_record["avg_temperature"]
                    humidity = gold_record["avg_humidity"]
                    # Simplified heat index approximation
                    if temp > 27:
                        heat_index = temp + 0.5555 * (
                            6.11 * pow(10, (7.5 * temp / (237.7 + temp))) - 10
                        )
                        gold_record["heat_index_avg"] = heat_index

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
        key = f"gold/terrestrial/{data_type}/{partition}/data_{self.ingestion_id}.json"

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
        logger.info(f"Starting terrestrial ingestion - Mode: {self.mode}")
        start_time = time.time()

        # 1. Ingest station metadata
        logger.info("Ingesting station metadata...")
        metadata = self.ingest_station_metadata()
        if metadata:
            self.write_bronze_layer(metadata, "metadata")
            silver_metadata = self.process_silver_layer(metadata, "metadata")
            self.write_silver_layer(silver_metadata, "metadata")
            self.write_gold_layer(silver_metadata, "metadata")

        # 2. Ingest station observations
        logger.info(
            f"Ingesting observations for {len(MAJOR_TERRESTRIAL_STATIONS)} stations..."
        )
        all_observations = []

        for i, station in enumerate(MAJOR_TERRESTRIAL_STATIONS):
            if i % 10 == 0:
                logger.info(
                    f"Processing station {i + 1}/{len(MAJOR_TERRESTRIAL_STATIONS)}: {station}"
                )

            observations = self.ingest_station_observations(station)
            if observations:
                all_observations.extend(observations)

            # Rate limiting
            time.sleep(0.5)

        # Write observations through medallion layers
        if all_observations:
            self.write_bronze_layer(all_observations, "observations")
            silver_obs = self.process_silver_layer(all_observations, "observations")
            self.write_silver_layer(silver_obs, "observations")
            gold_obs = self.process_gold_layer(silver_obs, "observations")
            self.write_gold_layer(gold_obs, "observations")

        # 3. Ingest fire weather alerts
        logger.info("Ingesting fire weather alerts...")
        fire_weather = self.ingest_fire_weather()
        if fire_weather:
            self.write_bronze_layer(fire_weather, "fire_weather")
            silver_fire = self.process_silver_layer(fire_weather, "fire_weather")
            self.write_silver_layer(silver_fire, "fire_weather")
            self.write_gold_layer(silver_fire, "fire_weather")

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

        logger.info(f"Lambda invoked - Mode: {mode}, Hours: {hours_back}")

        # Run ingestion
        ingestion = TerrestrialIngestion(mode=mode, hours_back=hours_back)
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
