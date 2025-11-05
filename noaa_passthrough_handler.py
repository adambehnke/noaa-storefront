"""
NOAA Passthrough Handler - Direct API Query Lambda

This Lambda function provides direct passthrough access to NOAA APIs when:
1. Gold layer doesn't have the requested data
2. User needs real-time data
3. Specific NOAA endpoints are requested

Supported Services:
- NWS (National Weather Service) - atmospheric data
- Tides & Currents (CO-OPS) - oceanic data
- CDO (Climate Data Online) - historical climate data

Usage:
    GET /passthrough?service=nws&endpoint=alerts/active
    GET /passthrough?service=tides&station=9414290&product=water_level
    GET /passthrough?service=cdo&dataset=GHCND&location=FIPS:06
"""

import json
import os
import logging
import boto3
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

# --- Logging setup ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- AWS Clients ---
secrets_client = boto3.client("secretsmanager")

# --- Environment Variables ---
ENV = os.environ.get("ENV", "dev")
CDO_TOKEN_SECRET = os.environ.get("NOAA_CDO_TOKEN_SECRET", "noaa-cdo-token-dev")

# --- API Configuration ---
NWS_BASE_URL = "https://api.weather.gov"
TIDES_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
CDO_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2"

REQUEST_TIMEOUT = 15
USER_AGENT = "NOAA-Federated-Lake/1.0"

# --- Cache for secrets ---
_cdo_token = None


# =============================================================
# Main Lambda Handler
# =============================================================
def lambda_handler(event, context):
    """
    Entry point for Lambda - routes queries to appropriate NOAA API

    Query parameters:
    - service: nws, tides, cdo (required)
    - endpoint: specific API endpoint (optional, defaults vary)
    - station: tide station ID (for tides service)
    - product: data product type (for tides service)
    - dataset: CDO dataset ID (for cdo service)
    - location: location ID (for cdo service)
    """

    try:
        # Parse event
        if isinstance(event, dict) and "queryStringParameters" in event:
            params = event.get("queryStringParameters") or {}
            http_method = event.get("httpMethod", "GET")
            path = event.get("path", "/passthrough")
        else:
            params = event if isinstance(event, dict) else {}
            http_method = "GET"
            path = "/passthrough"

        logger.info(f"Passthrough request: {http_method} {path} with params: {params}")

        # Get service type
        service = params.get("service", "").lower()

        if not service:
            return respond(
                400,
                {
                    "error": "Missing required parameter: service",
                    "valid_services": [
                        "nws",
                        "tides",
                        "cdo",
                        "atmospheric",
                        "oceanic",
                        "climate",
                    ],
                },
            )

        # Route to appropriate handler
        if service in ["nws", "atmospheric"]:
            return query_nws_api(params)
        elif service in ["tides", "oceanic", "coops"]:
            return query_tides_api(params)
        elif service in ["cdo", "climate", "ncei"]:
            return query_cdo_api(params)
        else:
            return respond(
                400,
                {
                    "error": f"Unknown service: {service}",
                    "valid_services": ["nws", "tides", "cdo"],
                },
            )

    except Exception as e:
        logger.exception("Unhandled exception in passthrough handler")
        return respond(500, {"error": str(e), "type": type(e).__name__})


# =============================================================
# NWS API Handler
# =============================================================
def query_nws_api(params: Dict) -> Dict:
    """
    Query National Weather Service API directly

    Examples:
    - alerts/active - All active weather alerts
    - alerts/active?area=CA - California alerts
    - points/37.7749,-122.4194 - Point forecast for San Francisco
    - stations/KSFO/observations/latest - Latest observation from SFO
    """

    endpoint = params.get("endpoint", "alerts/active")
    area = params.get("area")  # State code (e.g., CA)

    # Build URL
    url = f"{NWS_BASE_URL}/{endpoint}"

    # Add query parameters
    query_params = {}
    if area:
        query_params["area"] = area

    # Add any additional params (zone, point, etc.)
    for key in ["zone", "point", "state", "region", "type"]:
        if key in params:
            query_params[key] = params[key]

    logger.info(f"Querying NWS API: {url} with params: {query_params}")

    try:
        response = requests.get(
            url,
            params=query_params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()

            # Extract relevant info
            if "features" in data:
                features = data["features"]
                record_count = len(features)

                # Simplify if it's alerts
                if "alerts" in endpoint:
                    alerts_summary = []
                    for feature in features[:10]:  # First 10
                        props = feature.get("properties", {})
                        alerts_summary.append(
                            {
                                "event": props.get("event"),
                                "severity": props.get("severity"),
                                "area": props.get("areaDesc"),
                                "headline": props.get("headline"),
                            }
                        )

                    return respond(
                        200,
                        {
                            "source": "noaa_nws_api",
                            "service": "atmospheric",
                            "endpoint": endpoint,
                            "summary": {
                                "total_alerts": record_count,
                                "sample_alerts": alerts_summary,
                            },
                            "data": features,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )

            return respond(
                200,
                {
                    "source": "noaa_nws_api",
                    "service": "atmospheric",
                    "endpoint": endpoint,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        elif response.status_code == 404:
            return respond(
                404,
                {
                    "error": "NWS endpoint not found",
                    "endpoint": endpoint,
                    "message": "Check that the endpoint path is correct",
                },
            )

        else:
            return respond(
                response.status_code,
                {
                    "error": "NWS API error",
                    "status_code": response.status_code,
                    "details": response.text[:500],
                },
            )

    except requests.exceptions.Timeout:
        return respond(
            504,
            {
                "error": "NWS API timeout",
                "message": f"Request took longer than {REQUEST_TIMEOUT} seconds",
            },
        )

    except Exception as e:
        logger.exception("Error querying NWS API")
        return respond(500, {"error": "Failed to query NWS API", "details": str(e)})


# =============================================================
# Tides & Currents API Handler
# =============================================================
def query_tides_api(params: Dict) -> Dict:
    """
    Query NOAA Tides & Currents API (CO-OPS) directly

    Examples:
    - station=9414290&product=water_level - San Francisco water levels
    - station=8638610&product=predictions - Baltimore tide predictions
    - station=9414290&product=currents - San Francisco currents
    """

    # Required parameters
    station = params.get("station", "9414290")  # Default: San Francisco
    product = params.get("product", "water_level")  # Default: water level

    # Date range (default: last 24 hours)
    hours_back = int(params.get("hours_back", 24))
    begin_date = (datetime.utcnow() - timedelta(hours=hours_back)).strftime(
        "%Y%m%d %H:%M"
    )
    end_date = datetime.utcnow().strftime("%Y%m%d %H:%M")

    # Override with custom dates if provided
    if "begin_date" in params:
        begin_date = params["begin_date"]
    if "end_date" in params:
        end_date = params["end_date"]

    # Build query parameters
    query_params = {
        "product": product,
        "station": station,
        "begin_date": begin_date,
        "end_date": end_date,
        "time_zone": params.get("time_zone", "GMT"),
        "units": params.get("units", "metric"),
        "format": "json",
        "application": USER_AGENT,
    }

    # Add datum for water level products
    if product in ["water_level", "hourly_height", "high_low"]:
        query_params["datum"] = params.get("datum", "MLLW")

    logger.info(f"Querying Tides API: station={station}, product={product}")

    try:
        response = requests.get(
            TIDES_BASE_URL,
            params=query_params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()

            # Extract data points
            data_points = data.get("data", [])

            # Get metadata
            metadata = data.get("metadata", {})
            station_name = metadata.get("name", f"Station {station}")

            # Summary stats
            summary = {
                "station_id": station,
                "station_name": station_name,
                "product": product,
                "record_count": len(data_points),
                "date_range": {"start": begin_date, "end": end_date},
            }

            # Add value stats if available
            if data_points and "v" in data_points[0]:
                values = [float(d["v"]) for d in data_points if "v" in d]
                if values:
                    summary["statistics"] = {
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                    }

            return respond(
                200,
                {
                    "source": "noaa_tides_api",
                    "service": "oceanic",
                    "summary": summary,
                    "metadata": metadata,
                    "data": data_points,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        else:
            error_msg = (
                data.get("error", {}).get("message", "Unknown error")
                if "data" in locals()
                else response.text
            )
            return respond(
                response.status_code,
                {
                    "error": "Tides API error",
                    "status_code": response.status_code,
                    "message": error_msg[:500],
                },
            )

    except requests.exceptions.Timeout:
        return respond(
            504,
            {
                "error": "Tides API timeout",
                "message": f"Request took longer than {REQUEST_TIMEOUT} seconds",
            },
        )

    except Exception as e:
        logger.exception("Error querying Tides API")
        return respond(500, {"error": "Failed to query Tides API", "details": str(e)})


# =============================================================
# CDO (Climate Data Online) API Handler
# =============================================================
def query_cdo_api(params: Dict) -> Dict:
    """
    Query NOAA Climate Data Online API

    Requires: CDO API token (stored in Secrets Manager)

    Examples:
    - dataset=GHCND&location=FIPS:06 - Daily climate data for California
    - dataset=NORMAL_DLY&station=GHCND:USW00023174 - Climate normals for LAX
    """

    # Get API token
    token = get_cdo_token()
    if not token:
        return respond(
            500,
            {
                "error": "CDO API token not configured",
                "message": f"Token not found in Secrets Manager: {CDO_TOKEN_SECRET}",
            },
        )

    # Parameters
    dataset = params.get("dataset", "GHCND")  # Default: Daily Summaries
    location = params.get("location", "FIPS:06")  # Default: California

    # Date range (default: last 30 days)
    days_back = int(params.get("days_back", 30))
    start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = datetime.utcnow().strftime("%Y-%m-%d")

    if "start_date" in params:
        start_date = params["start_date"]
    if "end_date" in params:
        end_date = params["end_date"]

    # Build query params
    query_params = {
        "datasetid": dataset,
        "startdate": start_date,
        "enddate": end_date,
        "limit": int(params.get("limit", 100)),
    }

    # Add location or station
    if "station" in params:
        query_params["stationid"] = params["station"]
    elif location:
        query_params["locationid"] = location

    # Specific data types if requested
    if "datatypes" in params:
        query_params["datatypeid"] = params["datatypes"]

    logger.info(f"Querying CDO API: dataset={dataset}, location={location}")

    try:
        response = requests.get(
            f"{CDO_BASE_URL}/data",
            params=query_params,
            headers={"token": token, "User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()

            results = data.get("results", [])
            metadata = data.get("metadata", {})

            summary = {
                "dataset": dataset,
                "location": location,
                "record_count": len(results),
                "total_available": metadata.get("resultset", {}).get(
                    "count", len(results)
                ),
                "date_range": {"start": start_date, "end": end_date},
            }

            return respond(
                200,
                {
                    "source": "noaa_cdo_api",
                    "service": "climate",
                    "summary": summary,
                    "metadata": metadata,
                    "data": results,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        elif response.status_code == 429:
            return respond(
                429,
                {
                    "error": "CDO API rate limit exceeded",
                    "message": "Try again in a few minutes",
                },
            )

        else:
            return respond(
                response.status_code,
                {
                    "error": "CDO API error",
                    "status_code": response.status_code,
                    "details": response.text[:500],
                },
            )

    except requests.exceptions.Timeout:
        return respond(
            504,
            {
                "error": "CDO API timeout",
                "message": f"Request took longer than {REQUEST_TIMEOUT} seconds",
            },
        )

    except Exception as e:
        logger.exception("Error querying CDO API")
        return respond(500, {"error": "Failed to query CDO API", "details": str(e)})


# =============================================================
# Helper Functions
# =============================================================
def get_cdo_token() -> Optional[str]:
    """Get CDO API token from Secrets Manager or environment"""

    global _cdo_token

    if _cdo_token:
        return _cdo_token

    # Try environment variable first
    env_token = os.environ.get("NOAA_CDO_TOKEN")
    if env_token:
        _cdo_token = env_token
        return _cdo_token

    # Try Secrets Manager
    try:
        response = secrets_client.get_secret_value(SecretId=CDO_TOKEN_SECRET)
        _cdo_token = response.get("SecretString")
        logger.info("Retrieved CDO token from Secrets Manager")
        return _cdo_token
    except Exception as e:
        logger.warning(f"Could not retrieve CDO token from Secrets Manager: {e}")
        return None


def respond(status_code: int, body: Dict) -> Dict:
    """Format Lambda response for API Gateway"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


# =============================================================
# For local testing
# =============================================================
if __name__ == "__main__":
    # Test NWS
    print("=== Testing NWS API ===")
    result = lambda_handler(
        {
            "queryStringParameters": {
                "service": "nws",
                "endpoint": "alerts/active",
                "area": "CA",
            }
        },
        None,
    )
    print(json.dumps(json.loads(result["body"]), indent=2))

    # Test Tides
    print("\n=== Testing Tides API ===")
    result = lambda_handler(
        {
            "queryStringParameters": {
                "service": "tides",
                "station": "9414290",
                "product": "water_level",
                "hours_back": "6",
            }
        },
        None,
    )
    print(json.dumps(json.loads(result["body"]), indent=2))
