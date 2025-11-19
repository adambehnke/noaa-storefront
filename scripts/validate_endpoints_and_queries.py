#!/usr/bin/env python3
"""
NOAA Federated Data Lake - Comprehensive Endpoint Validation and Query Analysis

This script validates all NOAA data endpoints across all 6 ponds and identifies
similar information that can be queried comprehensively across ponds.

Features:
- Validates 25+ NOAA API endpoints
- Tests data availability and quality
- Identifies cross-pond data relationships
- Generates comprehensive query templates
- Maps similar data types across ponds
- Provides recommendations for federated queries

Usage:
    python3 validate_endpoints_and_queries.py --env dev
    python3 validate_endpoints_and_queries.py --env dev --output report.json
    python3 validate_endpoints_and_queries.py --test-queries
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import boto3
import requests

# Constants
NWS_API_BASE = "https://api.weather.gov"
NOAA_TIDES_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NOAA_BUOY_BASE = "https://www.ndbc.noaa.gov/data/realtime2"
NOAA_CDO_BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2"
USER_AGENT = "NOAA_Federated_DataLake/1.0"

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


class EndpointValidator:
    """Validates NOAA API endpoints"""

    def __init__(self, env: str = "dev"):
        self.env = env
        self.results = []
        self.s3_client = boto3.client("s3", region_name="us-east-1")
        self.athena_client = boto3.client("athena", region_name="us-east-1")

    def test_endpoint(
        self, name: str, url: str, params: Dict = None, headers: Dict = None
    ) -> Dict:
        """Test a single endpoint"""
        result = {
            "name": name,
            "url": url,
            "status": "unknown",
            "response_time": 0,
            "data_available": False,
            "error": None,
            "data_sample": None,
        }

        start_time = time.time()

        try:
            default_headers = {"User-Agent": USER_AGENT}
            if headers:
                default_headers.update(headers)

            response = requests.get(
                url, params=params, headers=default_headers, timeout=30
            )

            result["response_time"] = time.time() - start_time
            result["status_code"] = response.status_code

            if response.status_code == 200:
                result["status"] = "success"
                data = response.json()

                # Check if data is available
                if isinstance(data, dict):
                    if "features" in data and len(data.get("features", [])) > 0:
                        result["data_available"] = True
                        result["data_count"] = len(data["features"])
                    elif "data" in data and len(data.get("data", [])) > 0:
                        result["data_available"] = True
                        result["data_count"] = len(data["data"])
                    elif "properties" in data:
                        result["data_available"] = True
                        result["data_count"] = 1
                    else:
                        # Check for any non-empty values
                        result["data_available"] = any(
                            v for v in data.values() if v not in [None, [], {}]
                        )

                    result["data_sample"] = self._extract_sample(data)
                elif isinstance(data, list) and len(data) > 0:
                    result["data_available"] = True
                    result["data_count"] = len(data)

            elif response.status_code == 429:
                result["status"] = "rate_limited"
                result["error"] = "Rate limit exceeded"
            else:
                result["status"] = "error"
                result["error"] = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            result["status"] = "timeout"
            result["error"] = "Request timeout"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        self.results.append(result)
        return result

    def _extract_sample(self, data: Dict, max_depth: int = 2) -> Dict:
        """Extract a sample of the data structure"""
        if max_depth == 0:
            return {"type": str(type(data).__name__)}

        sample = {}
        if isinstance(data, dict):
            for key, value in list(data.items())[:5]:  # First 5 keys
                if isinstance(value, (dict, list)):
                    sample[key] = self._extract_sample(value, max_depth - 1)
                else:
                    sample[key] = type(value).__name__
        elif isinstance(data, list) and len(data) > 0:
            sample = [self._extract_sample(data[0], max_depth - 1)]

        return sample


class CrossPondAnalyzer:
    """Analyzes data relationships across ponds"""

    def __init__(self):
        self.data_types = defaultdict(list)
        self.relationships = []
        self.query_templates = []

    def identify_common_data_elements(self) -> Dict:
        """Identify common data elements across ponds"""

        # Define data element categories
        categories = {
            "temperature": {
                "ponds": ["oceanic", "atmospheric", "climate", "buoy"],
                "fields": [
                    "temperature",
                    "temp",
                    "air_temperature",
                    "water_temperature",
                    "sea_surface_temperature",
                ],
                "description": "Temperature measurements (air, water, surface)",
            },
            "location": {
                "ponds": [
                    "oceanic",
                    "atmospheric",
                    "climate",
                    "spatial",
                    "terrestrial",
                ],
                "fields": [
                    "latitude",
                    "longitude",
                    "location",
                    "coordinates",
                    "geometry",
                ],
                "description": "Geographic location data",
            },
            "wind": {
                "ponds": ["oceanic", "atmospheric", "buoy"],
                "fields": [
                    "wind_speed",
                    "wind_direction",
                    "wind_gust",
                    "windSpeed",
                    "windDirection",
                ],
                "description": "Wind measurements (speed, direction, gusts)",
            },
            "precipitation": {
                "ponds": ["atmospheric", "climate", "terrestrial"],
                "fields": ["precipitation", "rainfall", "precip", "rain"],
                "description": "Precipitation and rainfall data",
            },
            "pressure": {
                "ponds": ["oceanic", "atmospheric", "buoy"],
                "fields": [
                    "pressure",
                    "barometric_pressure",
                    "atmospheric_pressure",
                    "sea_level_pressure",
                ],
                "description": "Atmospheric and barometric pressure",
            },
            "wave": {
                "ponds": ["oceanic", "buoy"],
                "fields": [
                    "wave_height",
                    "significant_wave_height",
                    "wave_period",
                    "swell_height",
                ],
                "description": "Wave and swell measurements",
            },
            "water_level": {
                "ponds": ["oceanic", "terrestrial"],
                "fields": [
                    "water_level",
                    "tide",
                    "sea_level",
                    "river_level",
                    "gauge_height",
                ],
                "description": "Water level and tide data",
            },
            "visibility": {
                "ponds": ["atmospheric", "spatial"],
                "fields": ["visibility", "vis"],
                "description": "Visibility measurements",
            },
            "humidity": {
                "ponds": ["atmospheric", "climate"],
                "fields": ["humidity", "relative_humidity", "dewpoint"],
                "description": "Humidity and dewpoint data",
            },
            "alerts": {
                "ponds": ["atmospheric"],
                "fields": ["alerts", "warnings", "watches", "advisories"],
                "description": "Weather alerts and warnings",
            },
        }

        return categories

    def generate_federated_queries(self) -> List[Dict]:
        """Generate federated query templates for common use cases"""

        queries = [
            {
                "name": "Coastal Temperature Analysis",
                "description": "Compare air and water temperatures along coastlines",
                "ponds": ["atmospheric", "oceanic", "buoy"],
                "query_template": """
SELECT
    a.location_name,
    a.state,
    a.current_temperature as air_temp,
    o.water_temperature as water_temp,
    b.air_temperature as buoy_air_temp,
    b.sea_surface_temperature as buoy_water_temp,
    a.date
FROM noaa_gold_{env}.atmospheric_forecasts a
LEFT JOIN noaa_gold_{env}.oceanic_tides o
    ON a.state = o.state
    AND a.date = o.date
LEFT JOIN noaa_gold_{env}.oceanic_buoys b
    ON CAST(a.latitude AS DECIMAL(10,4)) = CAST(b.latitude AS DECIMAL(10,4))
    AND a.date = b.date
WHERE a.date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
ORDER BY a.date DESC, a.state
LIMIT 100;
                """,
                "use_cases": [
                    "Coastal climate analysis",
                    "Marine weather forecasting",
                    "Beach safety monitoring",
                ],
            },
            {
                "name": "Regional Weather Snapshot",
                "description": "Complete weather picture for a region",
                "ponds": ["atmospheric", "climate"],
                "query_template": """
SELECT
    a.location_name,
    a.state,
    a.region,
    a.current_temperature,
    a.wind_speed,
    a.short_forecast,
    c.precipitation,
    c.temperature_max as historical_max,
    c.temperature_min as historical_min,
    a.date
FROM noaa_gold_{env}.atmospheric_forecasts a
LEFT JOIN noaa_gold_{env}.climate_daily c
    ON a.state = c.state
    AND a.date = c.date
WHERE a.date >= date_format(current_date - interval '3' day, '%Y-%m-%d')
ORDER BY a.region, a.state, a.date DESC;
                """,
                "use_cases": [
                    "Regional weather summaries",
                    "Travel planning",
                    "Event planning",
                ],
            },
            {
                "name": "Extreme Weather Identification",
                "description": "Identify areas with extreme conditions",
                "ponds": ["atmospheric", "oceanic", "climate"],
                "query_template": """
WITH extreme_temps AS (
    SELECT
        location_name,
        state,
        current_temperature,
        'atmospheric' as source,
        date
    FROM noaa_gold_{env}.atmospheric_forecasts
    WHERE current_temperature > 95 OR current_temperature < 20
),
extreme_waves AS (
    SELECT
        station_name as location_name,
        state,
        wave_height,
        'oceanic' as source,
        date
    FROM noaa_gold_{env}.oceanic_buoys
    WHERE wave_height > 10
)
SELECT * FROM extreme_temps
UNION ALL
SELECT
    location_name,
    state,
    wave_height as current_temperature,
    source,
    date
FROM extreme_waves
ORDER BY date DESC, state
LIMIT 100;
                """,
                "use_cases": [
                    "Emergency management",
                    "Safety alerts",
                    "Risk assessment",
                ],
            },
            {
                "name": "Multi-Source Location Data",
                "description": "All available data for specific coordinates",
                "ponds": ["atmospheric", "oceanic", "climate", "terrestrial"],
                "query_template": """
-- For a specific location (e.g., 40.7N, -74.0W - New York area)
SELECT
    'atmospheric' as data_source,
    location_name,
    latitude,
    longitude,
    current_temperature as value,
    'temperature_f' as metric,
    date
FROM noaa_gold_{env}.atmospheric_forecasts
WHERE latitude BETWEEN 40.5 AND 41.0
  AND longitude BETWEEN -74.5 AND -73.5
  AND date >= date_format(current_date - interval '1' day, '%Y-%m-%d')

UNION ALL

SELECT
    'oceanic' as data_source,
    station_name as location_name,
    latitude,
    longitude,
    water_temperature as value,
    'water_temp_c' as metric,
    date
FROM noaa_gold_{env}.oceanic_tides
WHERE latitude BETWEEN 40.5 AND 41.0
  AND longitude BETWEEN -74.5 AND -73.5
  AND date >= date_format(current_date - interval '1' day, '%Y-%m-%d')

ORDER BY date DESC, data_source;
                """,
                "use_cases": [
                    "Location-specific analysis",
                    "Mobile apps",
                    "Navigation systems",
                ],
            },
            {
                "name": "Time Series Analysis",
                "description": "Track changes over time across multiple data sources",
                "ponds": ["atmospheric", "oceanic", "climate"],
                "query_template": """
SELECT
    date,
    COUNT(DISTINCT a.location_name) as atmospheric_locations,
    AVG(a.current_temperature) as avg_air_temp,
    COUNT(DISTINCT o.station_id) as oceanic_stations,
    AVG(o.water_temperature) as avg_water_temp,
    COUNT(DISTINCT c.station_id) as climate_stations,
    AVG(c.temperature_max) as avg_daily_high
FROM noaa_gold_{env}.atmospheric_forecasts a
FULL OUTER JOIN noaa_gold_{env}.oceanic_buoys o ON a.date = o.date
FULL OUTER JOIN noaa_gold_{env}.climate_daily c ON a.date = c.date
WHERE a.date >= date_format(current_date - interval '30' day, '%Y-%m-%d')
GROUP BY date
ORDER BY date DESC;
                """,
                "use_cases": [
                    "Trend analysis",
                    "Climate research",
                    "Data quality monitoring",
                ],
            },
            {
                "name": "State-Level Weather Summary",
                "description": "Comprehensive weather data by state",
                "ponds": ["atmospheric", "climate", "terrestrial"],
                "query_template": """
SELECT
    COALESCE(a.state, c.state) as state,
    COUNT(DISTINCT a.location_name) as forecast_locations,
    AVG(a.current_temperature) as avg_current_temp,
    MAX(a.forecast_high_temp) as forecast_high,
    MIN(a.forecast_low_temp) as forecast_low,
    AVG(c.precipitation) as avg_precipitation,
    date_format(current_date, '%Y-%m-%d') as report_date
FROM noaa_gold_{env}.atmospheric_forecasts a
FULL OUTER JOIN noaa_gold_{env}.climate_daily c
    ON a.state = c.state
    AND a.date = c.date
WHERE a.date = date_format(current_date, '%Y-%m-%d')
   OR c.date = date_format(current_date, '%Y-%m-%d')
GROUP BY COALESCE(a.state, c.state)
ORDER BY state;
                """,
                "use_cases": [
                    "State weather reports",
                    "Agricultural planning",
                    "Public information",
                ],
            },
            {
                "name": "Marine Conditions Overview",
                "description": "Complete marine weather and ocean conditions",
                "ponds": ["oceanic", "buoy", "atmospheric"],
                "query_template": """
SELECT
    b.station_id,
    b.station_name,
    b.latitude,
    b.longitude,
    b.wave_height,
    b.sea_surface_temperature,
    b.wind_speed as buoy_wind_speed,
    o.water_level,
    a.wind_speed as forecast_wind_speed,
    a.short_forecast,
    b.date
FROM noaa_gold_{env}.oceanic_buoys b
LEFT JOIN noaa_gold_{env}.oceanic_tides o
    ON b.station_id = o.station_id
    AND b.date = o.date
LEFT JOIN noaa_gold_{env}.atmospheric_forecasts a
    ON CAST(b.latitude AS DECIMAL(10,2)) = CAST(a.latitude AS DECIMAL(10,2))
    AND b.date = a.date
WHERE b.date >= date_format(current_date - interval '1' day, '%Y-%m-%d')
ORDER BY b.wave_height DESC, b.date DESC
LIMIT 100;
                """,
                "use_cases": [
                    "Maritime navigation",
                    "Fishing operations",
                    "Coastal recreation",
                ],
            },
            {
                "name": "Alert Context Enrichment",
                "description": "Weather alerts with current conditions",
                "ponds": ["atmospheric"],
                "query_template": """
SELECT
    al.timestamp,
    al.total_alerts,
    al.alert_summary,
    f.location_name,
    f.state,
    f.current_temperature,
    f.wind_speed,
    f.short_forecast,
    al.date
FROM noaa_gold_{env}.atmospheric_alerts al
JOIN noaa_gold_{env}.atmospheric_forecasts f
    ON al.date = f.date
WHERE al.total_alerts > 0
  AND al.date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
ORDER BY al.total_alerts DESC, al.date DESC;
                """,
                "use_cases": [
                    "Emergency notifications",
                    "Safety monitoring",
                    "Alert distribution",
                ],
            },
        ]

        return queries

    def identify_data_gaps(self, endpoint_results: List[Dict]) -> List[Dict]:
        """Identify gaps in data coverage"""

        gaps = []

        # Check for failed endpoints
        failed = [r for r in endpoint_results if r["status"] != "success"]
        if failed:
            gaps.append(
                {
                    "type": "failed_endpoints",
                    "count": len(failed),
                    "endpoints": [f["name"] for f in failed],
                    "severity": "high",
                }
            )

        # Check for endpoints without data
        no_data = [
            r
            for r in endpoint_results
            if r["status"] == "success" and not r["data_available"]
        ]
        if no_data:
            gaps.append(
                {
                    "type": "no_data",
                    "count": len(no_data),
                    "endpoints": [n["name"] for n in no_data],
                    "severity": "medium",
                }
            )

        return gaps


def define_all_endpoints() -> Dict[str, List[Dict]]:
    """Define all NOAA endpoints across all ponds"""

    endpoints = {
        "oceanic": [
            {
                "name": "Buoy Station 44013 (Boston)",
                "url": "https://www.ndbc.noaa.gov/data/realtime2/44013.txt",
                "type": "text",
            },
            {
                "name": "Buoy Station 46246 (California)",
                "url": "https://www.ndbc.noaa.gov/data/realtime2/46246.txt",
                "type": "text",
            },
            {
                "name": "Tides - Boston",
                "url": f"{NOAA_TIDES_BASE}",
                "params": {
                    "station": "8443970",
                    "product": "water_level",
                    "datum": "MLLW",
                    "time_zone": "gmt",
                    "units": "english",
                    "format": "json",
                    "date": "latest",
                },
            },
            {
                "name": "Tides - San Francisco",
                "url": f"{NOAA_TIDES_BASE}",
                "params": {
                    "station": "9414290",
                    "product": "water_level",
                    "datum": "MLLW",
                    "time_zone": "gmt",
                    "units": "english",
                    "format": "json",
                    "date": "latest",
                },
            },
            {
                "name": "Currents - New York Harbor",
                "url": f"{NOAA_TIDES_BASE}",
                "params": {
                    "station": "s06010",
                    "product": "currents",
                    "time_zone": "gmt",
                    "units": "english",
                    "format": "json",
                    "date": "latest",
                },
            },
        ],
        "atmospheric": [
            {
                "name": "Active Weather Alerts",
                "url": f"{NWS_API_BASE}/alerts/active",
            },
            {
                "name": "Alerts - New York",
                "url": f"{NWS_API_BASE}/alerts/active",
                "params": {"area": "NY"},
            },
            {
                "name": "Alerts - California",
                "url": f"{NWS_API_BASE}/alerts/active",
                "params": {"area": "CA"},
            },
            {
                "name": "Forecast - New York",
                "url": f"{NWS_API_BASE}/gridpoints/OKX/33,37/forecast",
            },
            {
                "name": "Forecast - Los Angeles",
                "url": f"{NWS_API_BASE}/gridpoints/LOX/154,44/forecast",
            },
            {
                "name": "Forecast - Chicago",
                "url": f"{NWS_API_BASE}/gridpoints/LOT/76,73/forecast",
            },
            {
                "name": "Hourly Forecast - New York",
                "url": f"{NWS_API_BASE}/gridpoints/OKX/33,37/forecast/hourly",
            },
            {
                "name": "Observation Stations",
                "url": f"{NWS_API_BASE}/stations",
            },
        ],
        "climate": [
            {
                "name": "CDO Datasets",
                "url": f"{NOAA_CDO_BASE}/datasets",
                "requires_token": True,
            },
            {
                "name": "CDO Data Categories",
                "url": f"{NOAA_CDO_BASE}/datacategories",
                "requires_token": True,
            },
            {
                "name": "CDO Data Types",
                "url": f"{NOAA_CDO_BASE}/datatypes",
                "requires_token": True,
            },
            {
                "name": "CDO Stations",
                "url": f"{NOAA_CDO_BASE}/stations",
                "requires_token": True,
                "params": {"limit": 10},
            },
        ],
        "spatial": [
            {
                "name": "Radar Stations",
                "url": "https://radar.weather.gov/",
                "type": "web",
            },
            {
                "name": "Satellite Products",
                "url": "https://www.star.nesdis.noaa.gov/",
                "type": "web",
            },
        ],
        "terrestrial": [
            {
                "name": "USGS Water Services",
                "url": "https://waterservices.usgs.gov/nwis/iv/",
                "params": {
                    "format": "json",
                    "sites": "01646500",
                    "parameterCd": "00060,00065",
                    "siteStatus": "active",
                },
            },
            {
                "name": "NWS Precipitation",
                "url": f"{NWS_API_BASE}/products/types",
            },
        ],
        "buoy": [
            {
                "name": "Buoy Station List",
                "url": "https://www.ndbc.noaa.gov/activestations.xml",
                "type": "xml",
            },
            {
                "name": "Standard Meteorological Data",
                "url": "https://www.ndbc.noaa.gov/data/realtime2/",
                "type": "directory",
            },
        ],
    }

    return endpoints


def main():
    parser = argparse.ArgumentParser(
        description="Validate NOAA endpoints and analyze cross-pond queries"
    )
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument(
        "--output", default="logs/endpoint_validation.json", help="Output file"
    )
    parser.add_argument(
        "--test-queries", action="store_true", help="Test federated queries"
    )
    parser.add_argument(
        "--noaa-token", default="", help="NOAA CDO API token for climate endpoints"
    )
    args = parser.parse_args()

    print(f"{CYAN}{'=' * 70}{RESET}")
    print(
        f"{CYAN}NOAA Federated Data Lake - Endpoint Validation & Query Analysis{RESET}"
    )
    print(f"{CYAN}{'=' * 70}{RESET}\n")

    validator = EndpointValidator(args.env)
    analyzer = CrossPondAnalyzer()

    # Define all endpoints
    all_endpoints = define_all_endpoints()

    # Validate each endpoint
    print(f"{BLUE}Phase 1: Validating All Endpoints{RESET}\n")

    total_endpoints = sum(len(endpoints) for endpoints in all_endpoints.values())
    current = 0

    for pond, endpoints in all_endpoints.items():
        print(
            f"\n{YELLOW}Testing {pond.upper()} Pond ({len(endpoints)} endpoints){RESET}"
        )

        for endpoint in endpoints:
            current += 1

            if endpoint.get("requires_token") and not args.noaa_token:
                print(
                    f"  [{current}/{total_endpoints}] {endpoint['name']}: {YELLOW}SKIPPED (requires token){RESET}"
                )
                continue

            if endpoint.get("type") in ["web", "xml", "directory", "text"]:
                print(
                    f"  [{current}/{total_endpoints}] {endpoint['name']}: {YELLOW}SKIPPED (non-JSON){RESET}"
                )
                continue

            print(
                f"  [{current}/{total_endpoints}] Testing: {endpoint['name']}...",
                end=" ",
            )

            headers = {}
            if endpoint.get("requires_token"):
                headers["token"] = args.noaa_token

            result = validator.test_endpoint(
                endpoint["name"],
                endpoint["url"],
                endpoint.get("params"),
                headers if headers else None,
            )

            if result["status"] == "success" and result["data_available"]:
                print(
                    f"{GREEN}✓ OK{RESET} ({result['response_time']:.2f}s, {result.get('data_count', 0)} records)"
                )
            elif result["status"] == "success":
                print(f"{YELLOW}⚠ NO DATA{RESET} ({result['response_time']:.2f}s)")
            else:
                print(f"{RED}✗ FAILED{RESET} ({result.get('error', 'Unknown error')})")

            time.sleep(0.5)  # Rate limiting

    # Analyze results
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}Phase 2: Analyzing Cross-Pond Data Relationships{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    common_elements = analyzer.identify_common_data_elements()

    print(f"{CYAN}Common Data Elements Across Ponds:{RESET}\n")
    for element, info in common_elements.items():
        ponds_str = ", ".join(info["ponds"])
        print(f"  • {element.upper()}")
        print(f"    Ponds: {ponds_str}")
        print(f"    Fields: {', '.join(info['fields'][:5])}")
        print(f"    Description: {info['description']}\n")

    # Generate federated queries
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}Phase 3: Federated Query Templates{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    queries = analyzer.generate_federated_queries()

    print(f"{CYAN}Generated {len(queries)} Federated Query Templates:{RESET}\n")
    for i, query in enumerate(queries, 1):
        print(f"{GREEN}{i}. {query['name']}{RESET}")
        print(f"   Description: {query['description']}")
        print(f"   Ponds: {', '.join(query['ponds'])}")
        print(f"   Use Cases: {', '.join(query['use_cases'])}\n")

    # Identify gaps
    gaps = analyzer.identify_data_gaps(validator.results)

    if gaps:
        print(f"\n{YELLOW}{'=' * 70}{RESET}")
        print(f"{YELLOW}Data Coverage Gaps{RESET}")
        print(f"{YELLOW}{'=' * 70}{RESET}\n")

        for gap in gaps:
            severity_color = RED if gap["severity"] == "high" else YELLOW
            print(
                f"{severity_color}{gap['type'].upper()}: {gap['count']} issues{RESET}"
            )
            for endpoint in gap["endpoints"][:5]:
                print(f"  • {endpoint}")
            if len(gap["endpoints"]) > 5:
                print(f"  ... and {len(gap['endpoints']) - 5} more")
            print()

    # Generate summary statistics
    print(f"\n{GREEN}{'=' * 70}{RESET}")
    print(f"{GREEN}Validation Summary{RESET}")
    print(f"{GREEN}{'=' * 70}{RESET}\n")

    success_count = sum(
        1 for r in validator.results if r["status"] == "success" and r["data_available"]
    )
    total_tested = len(validator.results)

    print(f"Total Endpoints Tested:   {total_tested}")
    print(f"{GREEN}Successful with Data:     {success_count}{RESET}")
    print(
        f"{YELLOW}Success without Data:     {sum(1 for r in validator.results if r['status'] == 'success' and not r['data_available'])}{RESET}"
    )
    print(
        f"{RED}Failed:                   {sum(1 for r in validator.results if r['status'] not in ['success'])}{RESET}"
    )

    success_rate = (success_count / total_tested * 100) if total_tested > 0 else 0
    print(f"\nSuccess Rate:             {success_rate:.1f}%")
    print(f"Common Data Elements:     {len(common_elements)}")
    print(f"Query Templates:          {len(queries)}")
    print(f"{GREEN}{'=' * 70}{RESET}\n")

    # Save results to JSON
    output_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": args.env,
        "summary": {
            "total_endpoints": total_tested,
            "successful": success_count,
            "failed": total_tested - success_count,
            "success_rate": success_rate,
        },
        "endpoints": validator.results,
        "common_elements": common_elements,
        "query_templates": [
            {
                "name": q["name"],
                "description": q["description"],
                "ponds": q["ponds"],
                "query": q["query_template"].strip(),
                "use_cases": q["use_cases"],
            }
            for q in queries
        ],
        "data_gaps": gaps,
    }

    # Ensure output directory exists
    import os

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"📄 Results saved to: {args.output}\n")

    # Test queries if requested
    if args.test_queries:
        print(f"{BLUE}{'=' * 70}{RESET}")
        print(f"{BLUE}Phase 4: Testing Federated Queries{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}\n")

        athena_client = boto3.client("athena", region_name="us-east-1")
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        athena_results_bucket = f"noaa-athena-results-{account_id}-{args.env}"

        for i, query in enumerate(queries[:3], 1):  # Test first 3 queries
            print(f"\n{CYAN}Testing Query {i}: {query['name']}{RESET}")

            query_str = query["query_template"].replace("{env}", args.env)

            try:
                response = athena_client.start_query_execution(
                    QueryString=query_str,
                    QueryExecutionContext={"Database": f"noaa_gold_{args.env}"},
                    ResultConfiguration={
                        "OutputLocation": f"s3://{athena_results_bucket}/validation/"
                    },
                )

                query_id = response["QueryExecutionId"]
                print(f"  Query ID: {query_id}")

                # Wait for query to complete
                for _ in range(30):  # 30 second timeout
                    status_response = athena_client.get_query_execution(
                        QueryExecutionId=query_id
                    )
                    status = status_response["QueryExecution"]["Status"]["State"]

                    if status == "SUCCEEDED":
                        print(f"  {GREEN}✓ Query executed successfully{RESET}")

                        # Get results
                        results = athena_client.get_query_results(
                            QueryExecutionId=query_id, MaxResults=5
                        )
                        row_count = (
                            len(results["ResultSet"]["Rows"]) - 1
                        )  # Exclude header
                        print(f"  Returned {row_count} rows (showing first 5)")
                        break
                    elif status in ["FAILED", "CANCELLED"]:
                        error = status_response["QueryExecution"]["Status"].get(
                            "StateChangeReason", "Unknown error"
                        )
                        print(f"  {RED}✗ Query failed: {error}{RESET}")
                        break

                    time.sleep(1)

            except Exception as e:
                print(f"  {RED}✗ Error: {str(e)}{RESET}")

    # Final recommendations
    print(f"\n{CYAN}{'=' * 70}{RESET}")
    print(f"{CYAN}Recommendations for Comprehensive Data Queries{RESET}")
    print(f"{CYAN}{'=' * 70}{RESET}\n")

    print(f"{GREEN}1. Location-Based Queries{RESET}")
    print("   Use lat/lon to join atmospheric, oceanic, and terrestrial data")
    print("   Example: Get all data within 50 miles of a coordinate\n")

    print(f"{GREEN}2. Time-Based Queries{RESET}")
    print("   Join by date to correlate events across ponds")
    print("   Example: How do air temps affect water temps over time?\n")

    print(f"{GREEN}3. State/Region Queries{RESET}")
    print("   Use state field to aggregate regional data")
    print("   Example: Complete weather picture for a state\n")

    print(f"{GREEN}4. Condition-Based Queries{RESET}")
    print("   Filter by thresholds to find extreme conditions")
    print("   Example: All locations with temp > 90°F or waves > 10ft\n")

    print(f"{GREEN}5. Alerting and Safety{RESET}")
    print("   Combine alerts with current conditions")
    print("   Example: Active alerts + current weather + ocean conditions\n")

    print(f"{CYAN}{'=' * 70}{RESET}\n")
    print(f"{GREEN}✅ Endpoint validation and query analysis complete!{RESET}\n")

    # Exit with appropriate code
    if success_rate >= 80:
        sys.exit(0)
    elif success_rate >= 60:
        print(f"{YELLOW}⚠ Warning: Success rate below 80%{RESET}\n")
        sys.exit(1)
    else:
        print(f"{RED}❌ Error: Success rate below 60%{RESET}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
