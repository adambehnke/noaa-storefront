"""
NOAA Climate Data Ingestion Lambda
Implements Medallion Architecture: Bronze -> Silver -> Gold
Ingests historical climate data from NOAA NCEI (National Centers for Environmental Information)
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

# NOAA NCEI API Configuration
NCEI_BASE_URL = "https://www.ncei.noaa.gov/cdo-web/api/v2"
NCEI_TOKEN = os.environ.get("NCEI_TOKEN", "")  # Get from environment

# Major US climate stations for comprehensive coverage
MAJOR_CLIMATE_STATIONS = [
    "GHCND:USW00014739",  # Boston, MA
    "GHCND:USW00094728",  # New York JFK
    "GHCND:USW00013739",  # Philadelphia, PA
    "GHCND:USW00013743",  # Washington DC
    "GHCND:USW00013874",  # Atlanta, GA
    "GHCND:USW00012839",  # Miami, FL
    "GHCND:USW00094846",  # Chicago O'Hare
    "GHCND:USW00003927",  # Dallas/Fort Worth
    "GHCND:USW00003017",  # Denver, CO
    "GHCND:USW00023183",  # Phoenix, AZ
    "GHCND:USW00023174",  # Los Angeles, CA
    "GHCND:USW00023234",  # San Francisco, CA
    "GHCND:USW00024233",  # Seattle-Tacoma, WA
    "GHCND:USW00024229",  # Portland, OR
    "GHCND:USW00023169",  # Las Vegas, NV
    "GHCND:USW00024127",  # Salt Lake City, UT
    "GHCND:USW00014922",  # Minneapolis, MN
    "GHCND:USW00094847",  # Detroit, MI
    "GHCND:USW00013881",  # Charlotte, NC
    "GHCND:USW00012815",  # Orlando, FL
    "GHCND:USW00013897",  # Nashville, TN
    "GHCND:USW00013994",  # St. Louis, MO
    "GHCND:USW00014820",  # Cleveland, OH
    "GHCND:USW00094823",  # Pittsburgh, PA
    "GHCND:USW00012960",  # Houston, TX
    "GHCND:USW00013904",  # Austin, TX
    "GHCND:USW00013958",  # San Antonio, TX
    "GHCND:USW00013967",  # Oklahoma City, OK
    "GHCND:USW00003947",  # Kansas City, MO
    "GHCND:USW00093721",  # Baltimore, MD
]

# Climate data types
CLIMATE_DATATYPES = [
    "TMAX",  # Maximum temperature
    "TMIN",  # Minimum temperature
    "TAVG",  # Average temperature
    "PRCP",  # Precipitation
    "SNOW",  # Snowfall
    "SNWD",  # Snow depth
    "AWND",  # Average wind speed
    "WSF2",  # Fastest 2-minute wind speed
    "WT01",  # Fog
    "WT02",  # Heavy fog
    "WT03",  # Thunder
    "WT04",  # Ice pellets
    "WT05",  # Hail
    "WT06",  # Glaze or rime
    "WT08",  # Smoke or haze
    "WT09",  # Blowing snow
]


class ClimateIngestion:
    """Handles climate data ingestion with medallion architecture"""

    def __init__(self, mode="incremental", days_back=7, years_back=None):
        self.mode = mode
        self.days_back = days_back
        self.years_back = years_back
        self.session = requests.Session()

        # NCEI requires token authentication
        if NCEI_TOKEN:
            self.session.headers.update({"token": NCEI_TOKEN})

        self.session.headers.update(
            {"User-Agent": "NOAA-Federated-Data-Lake/1.0", "Accept": "application/json"}
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
        """Fetch data from NCEI API with retry logic"""
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
                elif response.status_code == 400:
                    logger.warning(f"Bad request for {url}: {response.text[:200]}")
                    return None
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

    def ingest_station_data(
        self,
        station_id: str,
        start_date: datetime,
        end_date: datetime,
        datatypes: List[str] = None,
    ) -> List[Dict]:
        """Ingest climate data for a specific station"""
        records = []

        if not NCEI_TOKEN:
            logger.warning("NCEI_TOKEN not set, skipping API calls")
            return records

        # NCEI limits to 1000 results per request
        url = f"{NCEI_BASE_URL}/data"

        # Use specific datatypes or all
        datatype_str = ",".join(datatypes) if datatypes else ",".join(CLIMATE_DATATYPES)

        params = {
            "datasetid": "GHCND",  # Global Historical Climatology Network - Daily
            "stationid": station_id,
            "startdate": start_date.strftime("%Y-%m-%d"),
            "enddate": end_date.strftime("%Y-%m-%d"),
            "datatypeid": datatype_str,
            "units": "metric",
            "limit": 1000,
            "offset": 1,
        }

        # Paginate through results
        offset = 1
        while True:
            params["offset"] = offset

            data = self.fetch_with_retry(url, params=params)
            if not data or "results" not in data:
                break

            for result in data["results"]:
                try:
                    record = {
                        "record_id": hashlib.md5(
                            f"{result.get('station')}_{result.get('date')}_{result.get('datatype')}".encode()
                        ).hexdigest(),
                        "station_id": result.get("station"),
                        "date": result.get("date"),
                        "datatype": result.get("datatype"),
                        "value": self.safe_float(result.get("value")),
                        "attributes": result.get("attributes"),
                        "ingestion_timestamp": datetime.utcnow().isoformat(),
                        "ingestion_id": self.ingestion_id,
                        "data_source": "NOAA_NCEI",
                        "raw_json": json.dumps(result),
                    }
                    records.append(record)
                except Exception as e:
                    logger.error(f"Error processing climate record: {str(e)}")
                    self.stats["errors"] += 1

            # Check if there are more results
            if "metadata" in data and "resultset" in data["metadata"]:
                count = data["metadata"]["resultset"].get("count", 0)
                if offset + 1000 > count:
                    break
                offset += 1000
            else:
                break

            # Rate limiting
            time.sleep(0.2)

        return records

    def ingest_station_metadata(self) -> List[Dict]:
        """Ingest climate station metadata"""
        records = []

        if not NCEI_TOKEN:
            logger.warning("NCEI_TOKEN not set, using fallback metadata")
            # Return basic metadata for known stations
            for station_id in MAJOR_CLIMATE_STATIONS:
                records.append(
                    {
                        "station_id": station_id,
                        "name": station_id.split(":")[-1],
                        "ingestion_timestamp": datetime.utcnow().isoformat(),
                        "ingestion_id": self.ingestion_id,
                        "data_source": "NOAA_NCEI",
                    }
                )
            return records

        url = f"{NCEI_BASE_URL}/stations"

        for station_id in MAJOR_CLIMATE_STATIONS:
            params = {
                "stationid": station_id,
                "limit": 1,
            }

            data = self.fetch_with_retry(url, params=params)
            if not data or "results" not in data:
                continue

            for station in data["results"]:
                try:
                    record = {
                        "station_id": station.get("id"),
                        "name": station.get("name"),
                        "latitude": self.safe_float(station.get("latitude")),
                        "longitude": self.safe_float(station.get("longitude")),
                        "elevation": self.safe_float(station.get("elevation")),
                        "min_date": station.get("mindate"),
                        "max_date": station.get("maxdate"),
                        "datacoverage": self.safe_float(station.get("datacoverage")),
                        "ingestion_timestamp": datetime.utcnow().isoformat(),
                        "ingestion_id": self.ingestion_id,
                        "data_source": "NOAA_NCEI",
                        "raw_json": json.dumps(station),
                    }
                    records.append(record)
                except Exception as e:
                    logger.error(f"Error processing station metadata: {str(e)}")
                    self.stats["errors"] += 1

            # Rate limiting
            time.sleep(0.2)

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
        key = f"bronze/climate/{data_type}/{partition}/data_{self.ingestion_id}.json"

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

                # Parse date
                if cleaned.get("date"):
                    try:
                        dt = datetime.fromisoformat(cleaned["date"].replace("Z", ""))
                        cleaned["year"] = dt.year
                        cleaned["month"] = dt.month
                        cleaned["day"] = dt.day
                        cleaned["date_parsed"] = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                # Convert temperature values (NCEI uses tenths of degrees Celsius)
                datatype = cleaned.get("datatype", "")
                if datatype in ["TMAX", "TMIN", "TAVG"] and cleaned.get("value"):
                    cleaned["temperature_celsius"] = cleaned["value"] / 10.0
                    cleaned["temperature_fahrenheit"] = (
                        cleaned["value"] / 10.0
                    ) * 9 / 5 + 32

                # Convert precipitation (tenths of mm)
                elif datatype == "PRCP" and cleaned.get("value"):
                    cleaned["precipitation_mm"] = cleaned["value"] / 10.0
                    cleaned["precipitation_inches"] = (cleaned["value"] / 10.0) / 25.4

                # Convert snow (mm)
                elif datatype in ["SNOW", "SNWD"] and cleaned.get("value"):
                    cleaned["snow_mm"] = cleaned["value"]
                    cleaned["snow_inches"] = cleaned["value"] / 25.4

                # Data quality flags
                cleaned["has_value"] = cleaned.get("value") is not None
                cleaned["is_temperature"] = datatype in ["TMAX", "TMIN", "TAVG"]
                cleaned["is_precipitation"] = datatype == "PRCP"
                cleaned["is_snow"] = datatype in ["SNOW", "SNWD"]
                cleaned["is_wind"] = datatype in ["AWND", "WSF2"]
                cleaned["is_weather_event"] = datatype.startswith("WT")

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
        key = f"silver/climate/{data_type}/{partition}/data_{self.ingestion_id}.json"

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

        # Group by station and date
        station_date_groups = {}
        for record in silver_records:
            station = record.get("station_id")
            date = record.get("date_parsed", record.get("date", "")[:10])
            key = f"{station}_{date}"

            if key not in station_date_groups:
                station_date_groups[key] = []
            station_date_groups[key].append(record)

        # Create aggregated daily records
        for key, group in station_date_groups.items():
            try:
                # Extract values by type
                tmax = next(
                    (
                        r.get("temperature_celsius")
                        for r in group
                        if r.get("datatype") == "TMAX"
                    ),
                    None,
                )
                tmin = next(
                    (
                        r.get("temperature_celsius")
                        for r in group
                        if r.get("datatype") == "TMIN"
                    ),
                    None,
                )
                tavg = next(
                    (
                        r.get("temperature_celsius")
                        for r in group
                        if r.get("datatype") == "TAVG"
                    ),
                    None,
                )
                prcp = next(
                    (
                        r.get("precipitation_mm")
                        for r in group
                        if r.get("datatype") == "PRCP"
                    ),
                    None,
                )
                snow = next(
                    (r.get("snow_mm") for r in group if r.get("datatype") == "SNOW"),
                    None,
                )
                snwd = next(
                    (r.get("snow_mm") for r in group if r.get("datatype") == "SNWD"),
                    None,
                )

                # Calculate tavg if not provided
                if tavg is None and tmax is not None and tmin is not None:
                    tavg = (tmax + tmin) / 2

                gold_record = {
                    "station_id": group[0]["station_id"],
                    "date": group[0].get("date_parsed", group[0].get("date", "")[:10]),
                    "year": group[0].get("year"),
                    "month": group[0].get("month"),
                    "day": group[0].get("day"),
                    "observation_count": len(group),
                    # Temperature
                    "temperature_max_c": tmax,
                    "temperature_min_c": tmin,
                    "temperature_avg_c": tavg,
                    "temperature_range_c": (tmax - tmin) if (tmax and tmin) else None,
                    # Precipitation
                    "precipitation_mm": prcp,
                    "has_precipitation": prcp is not None and prcp > 0,
                    # Snow
                    "snowfall_mm": snow,
                    "snow_depth_mm": snwd,
                    "has_snow": (snow is not None and snow > 0)
                    or (snwd is not None and snwd > 0),
                    # Weather events
                    "weather_events": [
                        r.get("datatype") for r in group if r.get("is_weather_event")
                    ],
                    "extreme_event_count": len(
                        [r for r in group if r.get("is_weather_event")]
                    ),
                    # Data quality
                    "data_completeness": len([r for r in group if r.get("has_value")])
                    / len(group),
                    "ingestion_timestamp": datetime.utcnow().isoformat(),
                }

                # Add climate indicators
                if tavg is not None:
                    gold_record["heating_degree_days"] = max(
                        0, 18.3 - tavg
                    )  # Base 65°F = 18.3°C
                    gold_record["cooling_degree_days"] = max(0, tavg - 18.3)

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
        key = f"gold/climate/{data_type}/{partition}/data_{self.ingestion_id}.json"

        try:
            # Convert weather_events lists to JSON strings for Athena
            for record in records:
                if "weather_events" in record:
                    record["weather_events"] = json.dumps(record["weather_events"])

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
        logger.info(f"Starting climate ingestion - Mode: {self.mode}")
        start_time = time.time()

        # Calculate time range
        end_date = datetime.utcnow()
        if self.mode == "backfill" and self.years_back:
            start_date = end_date - timedelta(days=self.years_back * 365)
        else:
            start_date = end_date - timedelta(days=self.days_back)

        logger.info(f"Time range: {start_date.date()} to {end_date.date()}")

        # 1. Ingest station metadata
        logger.info("Ingesting station metadata...")
        metadata = self.ingest_station_metadata()
        if metadata:
            self.write_bronze_layer(metadata, "metadata")
            silver_metadata = self.process_silver_layer(metadata, "metadata")
            self.write_silver_layer(silver_metadata, "metadata")
            self.write_gold_layer(silver_metadata, "metadata")

        # 2. Ingest climate observations
        logger.info(
            f"Ingesting climate data for {len(MAJOR_CLIMATE_STATIONS)} stations..."
        )
        all_observations = []

        for i, station in enumerate(MAJOR_CLIMATE_STATIONS):
            if i % 5 == 0:
                logger.info(
                    f"Processing station {i + 1}/{len(MAJOR_CLIMATE_STATIONS)}: {station}"
                )

            observations = self.ingest_station_data(station, start_date, end_date)
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
        days_back = event.get("days_back", 7)
        years_back = event.get("years_back")

        logger.info(
            f"Lambda invoked - Mode: {mode}, Days: {days_back}, Years: {years_back}"
        )

        # Run ingestion
        ingestion = ClimateIngestion(
            mode=mode, days_back=days_back, years_back=years_back
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
