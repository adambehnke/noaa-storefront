#!/usr/bin/env python3
"""
NOAA API Connectivity Test Script

This script tests connectivity to all NOAA APIs used in the federated data lake:
1. NWS API (National Weather Service) - Atmospheric data
2. Tides & Currents API (CO-OPS) - Oceanic data
3. CDO API (Climate Data Online) - Climate data

Run this BEFORE deploying the stack to ensure API access is working.

Usage:
    python3 test_noaa_apis.py

    # With CDO token
    NOAA_CDO_TOKEN=your_token python3 test_noaa_apis.py
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# ANSI color codes for pretty output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# API Configuration
NWS_BASE_URL = "https://api.weather.gov"
COOPS_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
CDO_BASE_URL = "https://www.ncdc.noaa.gov/cdo-web/api/v2"

REQUEST_TIMEOUT = 15


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{BLUE}{BOLD}{'=' * 70}{RESET}")
    print(f"{BLUE}{BOLD}{text}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    """Print error message"""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{YELLOW}⚠{RESET} {text}")


def print_info(text: str):
    """Print info message"""
    print(f"{BLUE}ℹ{RESET} {text}")


def test_nws_api() -> Dict[str, bool]:
    """
    Test National Weather Service API endpoints

    Returns:
        Dictionary with test results
    """
    print_header("Testing NWS API (National Weather Service)")
    results = {}

    # Test 1: Active Alerts
    print_info("Testing active alerts endpoint...")
    try:
        headers = {
            "User-Agent": "NOAA-Federated-Lake-Test/1.0",
            "Accept": "application/geo+json",
        }
        response = requests.get(
            f"{NWS_BASE_URL}/alerts/active", headers=headers, timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            alert_count = len(data.get("features", []))
            print_success(f"Active alerts: {alert_count} alerts retrieved")
            print_info(
                f"  Sample alert: {data['features'][0]['properties']['event'] if alert_count > 0 else 'None'}"
            )
            results["alerts"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["alerts"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["alerts"] = False

    # Test 2: Weather Stations
    print_info("Testing weather stations endpoint...")
    try:
        response = requests.get(
            f"{NWS_BASE_URL}/stations/KSFO/observations/latest",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            props = data.get("properties", {})
            temp = props.get("temperature", {}).get("value")
            desc = props.get("textDescription", "N/A")
            print_success(f"Station KSFO (San Francisco): {desc}, Temp: {temp}°C")
            results["observations"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["observations"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["observations"] = False

    # Test 3: Forecast Zones
    print_info("Testing forecast zones endpoint...")
    try:
        response = requests.get(
            f"{NWS_BASE_URL}/zones?type=forecast&limit=5",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            zone_count = len(data.get("features", []))
            print_success(f"Forecast zones: {zone_count} zones retrieved")
            results["forecast_zones"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["forecast_zones"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["forecast_zones"] = False

    # Test 4: Radar Stations
    print_info("Testing radar stations endpoint...")
    try:
        response = requests.get(
            f"{NWS_BASE_URL}/radar/stations", headers=headers, timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            data = response.json()
            radar_count = len(data.get("features", []))
            print_success(f"Radar stations: {radar_count} stations retrieved")
            results["radar_stations"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["radar_stations"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["radar_stations"] = False

    return results


def test_tides_api() -> Dict[str, bool]:
    """
    Test NOAA Tides & Currents (CO-OPS) API

    Returns:
        Dictionary with test results
    """
    print_header("Testing Tides & Currents API (CO-OPS)")
    results = {}

    # Time range for tests
    end_date = datetime.utcnow()
    begin_date = end_date - timedelta(hours=6)

    # Test 1: Water Levels
    print_info("Testing water levels endpoint...")
    try:
        params = {
            "product": "water_level",
            "application": "NOAA_Federated_Lake_Test",
            "begin_date": begin_date.strftime("%Y%m%d %H:%M"),
            "end_date": end_date.strftime("%Y%m%d %H:%M"),
            "station": "9414290",  # San Francisco
            "time_zone": "GMT",
            "units": "metric",
            "format": "json",
            "datum": "MLLW",
        }

        response = requests.get(COOPS_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                print_error(f"API Error: {data['error']}")
                results["water_levels"] = False
            else:
                record_count = len(data.get("data", []))
                print_success(
                    f"Water levels: {record_count} records retrieved for San Francisco"
                )
                if record_count > 0:
                    latest = data["data"][-1]
                    print_info(
                        f"  Latest reading: {latest.get('v')} meters at {latest.get('t')}"
                    )
                results["water_levels"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["water_levels"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["water_levels"] = False

    # Test 2: Water Temperature
    print_info("Testing water temperature endpoint...")
    try:
        params["product"] = "water_temperature"
        response = requests.get(COOPS_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                print_warning(
                    f"API Error: {data['error']} (Some stations may not have this data)"
                )
                results["water_temperature"] = False
            else:
                record_count = len(data.get("data", []))
                print_success(f"Water temperature: {record_count} records retrieved")
                results["water_temperature"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["water_temperature"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["water_temperature"] = False

    # Test 3: Wind Data
    print_info("Testing wind data endpoint...")
    try:
        params["product"] = "wind"
        response = requests.get(COOPS_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                print_warning(f"API Error: {data['error']}")
                results["wind"] = False
            else:
                record_count = len(data.get("data", []))
                print_success(f"Wind data: {record_count} records retrieved")
                results["wind"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["wind"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["wind"] = False

    # Test 4: Tide Predictions
    print_info("Testing tide predictions endpoint...")
    try:
        predict_end = datetime.utcnow() + timedelta(days=2)
        predict_begin = datetime.utcnow()

        params = {
            "product": "predictions",
            "application": "NOAA_Federated_Lake_Test",
            "begin_date": predict_begin.strftime("%Y%m%d %H:%M"),
            "end_date": predict_end.strftime("%Y%m%d %H:%M"),
            "station": "9414290",
            "time_zone": "GMT",
            "units": "metric",
            "format": "json",
            "datum": "MLLW",
            "interval": "hilo",
        }

        response = requests.get(COOPS_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                print_error(f"API Error: {data['error']}")
                results["predictions"] = False
            else:
                prediction_count = len(data.get("predictions", []))
                print_success(
                    f"Tide predictions: {prediction_count} predictions retrieved"
                )
                results["predictions"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["predictions"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["predictions"] = False

    return results


def test_cdo_api() -> Dict[str, bool]:
    """
    Test Climate Data Online (CDO) API
    Requires API token from environment variable NOAA_CDO_TOKEN

    Returns:
        Dictionary with test results
    """
    print_header("Testing CDO API (Climate Data Online)")
    results = {}

    # Check for API token
    api_token = os.environ.get("NOAA_CDO_TOKEN")
    if not api_token:
        print_warning("NOAA_CDO_TOKEN not set in environment")
        print_info("Get your token at: https://www.ncdc.noaa.gov/cdo-web/token")
        print_info("Then run: export NOAA_CDO_TOKEN=your_token")
        print_warning("Skipping CDO API tests")
        return {"token_available": False}

    print_success(f"API Token found: {api_token[:8]}...")

    headers = {"token": api_token}

    # Test 1: Datasets
    print_info("Testing datasets endpoint...")
    try:
        response = requests.get(
            f"{CDO_BASE_URL}/datasets",
            headers=headers,
            params={"limit": 5},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            dataset_count = len(data.get("results", []))
            print_success(f"Datasets: {dataset_count} datasets retrieved")
            if dataset_count > 0:
                print_info(f"  Example: {data['results'][0].get('name', 'N/A')}")
            results["datasets"] = True
        elif response.status_code == 401:
            print_error("Authentication failed - Invalid API token")
            results["datasets"] = False
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["datasets"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["datasets"] = False

    # Test 2: Data Types
    print_info("Testing data types endpoint...")
    try:
        response = requests.get(
            f"{CDO_BASE_URL}/datatypes",
            headers=headers,
            params={"limit": 5},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            type_count = len(data.get("results", []))
            print_success(f"Data types: {type_count} types retrieved")
            results["datatypes"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["datatypes"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["datatypes"] = False

    # Test 3: Actual Data (last 7 days)
    print_info("Testing data retrieval endpoint...")
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        params = {
            "datasetid": "GHCND",
            "locationid": "CITY:US480019",  # Austin, TX
            "startdate": start_date.strftime("%Y-%m-%d"),
            "enddate": end_date.strftime("%Y-%m-%d"),
            "limit": 10,
        }

        response = requests.get(
            f"{CDO_BASE_URL}/data",
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            record_count = len(data.get("results", []))
            print_success(f"Climate data: {record_count} records retrieved")
            if record_count > 0:
                print_info(
                    f"  Date range: {params['startdate']} to {params['enddate']}"
                )
            results["data"] = True
        else:
            print_error(f"Failed with status code: {response.status_code}")
            results["data"] = False

    except Exception as e:
        print_error(f"Exception: {str(e)}")
        results["data"] = False

    return results


def print_summary(nws_results: Dict, tides_results: Dict, cdo_results: Dict):
    """Print overall test summary"""
    print_header("Test Summary")

    all_tests = {
        "NWS API": nws_results,
        "Tides & Currents API": tides_results,
        "CDO API": cdo_results,
    }

    total_tests = 0
    passed_tests = 0

    for api_name, results in all_tests.items():
        print(f"\n{BOLD}{api_name}:{RESET}")
        for test_name, passed in results.items():
            total_tests += 1
            if passed:
                passed_tests += 1
                print_success(f"{test_name}")
            else:
                print_error(f"{test_name}")

    print(f"\n{BOLD}Overall Results:{RESET}")
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    if success_rate == 100:
        print_success(f"All tests passed! ({passed_tests}/{total_tests})")
        print_success("✓ You're ready to deploy the NOAA stack!")
    elif success_rate >= 75:
        print_warning(
            f"Most tests passed ({passed_tests}/{total_tests}, {success_rate:.1f}%)"
        )
        print_info("You can proceed with deployment, but some features may not work.")
    else:
        print_error(
            f"Many tests failed ({passed_tests}/{total_tests}, {success_rate:.1f}%)"
        )
        print_warning("Fix API connectivity issues before deploying.")

    # Recommendations
    print(f"\n{BOLD}Recommendations:{RESET}")

    if not cdo_results.get("token_available", True):
        print_info("• Get a CDO API token: https://www.ncdc.noaa.gov/cdo-web/token")

    if not all(nws_results.values()):
        print_info("• Check NWS API rate limits (max 5 requests/second)")
        print_info("• Ensure internet connectivity to api.weather.gov")

    if not all(tides_results.values()):
        print_info("• Some tidal stations may not support all data products")
        print_info(
            "• Water temperature and wind data may not be available at all stations"
        )

    print("")


def main():
    """Main test execution"""
    print(f"\n{BOLD}NOAA API Connectivity Test{RESET}")
    print(f"Testing connectivity to NOAA APIs before deployment...\n")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z\n")

    # Run all tests
    nws_results = test_nws_api()
    tides_results = test_tides_api()
    cdo_results = test_cdo_api()

    # Print summary
    print_summary(nws_results, tides_results, cdo_results)

    # Exit code based on critical tests
    critical_passed = (
        nws_results.get("alerts", False)
        and nws_results.get("observations", False)
        and tides_results.get("water_levels", False)
    )

    if critical_passed:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
