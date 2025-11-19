#!/usr/bin/env python3
"""
Maritime Route Planning Test Script
Tests the integration of alerts and stations ponds for maritime navigation

This script validates:
- Alerts pond queries for marine weather advisories
- Stations pond queries for observation point locations
- Multi-pond maritime route planning queries
- Data synthesis across atmospheric, oceanic, buoy, alerts, and stations ponds
"""

import json
import sys
import time
from datetime import datetime
from typing import Any, Dict

import boto3

# AWS Configuration
REGION = "us-east-1"
LAMBDA_FUNCTION_NAME = "noaa-intelligent-orchestrator-dev"

# Initialize boto3 client
lambda_client = boto3.client("lambda", region_name=REGION)


def invoke_lambda(query: str) -> Dict[Any, Any]:
    """Invoke the intelligent orchestrator Lambda function"""
    print(f"\n{'=' * 80}")
    print(f"QUERY: {query}")
    print(f"{'=' * 80}")

    start_time = time.time()

    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({"query": query}),
        )

        duration = time.time() - start_time

        payload = json.loads(response["Payload"].read())

        # Handle Lambda response format (API Gateway format with body)
        if "body" in payload and isinstance(payload["body"], str):
            payload = json.loads(payload["body"])

        print(f"\n✓ Lambda invocation successful ({duration:.2f}s)")
        print(f"Status Code: {response['StatusCode']}")

        return payload

    except Exception as e:
        print(f"\n✗ Lambda invocation failed: {str(e)}")
        return {"error": str(e)}


def print_response(response: Dict[Any, Any], show_full: bool = False):
    """Pretty print the response"""
    print("\n" + "─" * 80)
    print("RESPONSE:")
    print("─" * 80)

    if "error" in response:
        print(f"❌ ERROR: {response['error']}")
        return

    # Print metadata
    if "metadata" in response:
        metadata = response["metadata"]
        print(f"\n📊 Metadata:")
        print(f"  • Ponds Queried: {metadata.get('ponds_queried', 0)}")
        print(f"  • Execution Time: {metadata.get('execution_time_ms', 0):.0f}ms")
        print(f"  • Total Records: {metadata.get('total_records', 0)}")

    # Print pond results summary
    if "ponds_queried" in response:
        print(f"\n🗂️  Pond Results:")
        for pond_result in response["ponds_queried"]:
            pond_name = pond_result.get("pond", "Unknown")
            success = pond_result.get("success", False)
            record_count = pond_result.get("records_found", 0)
            relevance = pond_result.get("relevance_score", 0)

            status = "✓" if success else "✗"
            print(
                f"  {status} {pond_name}: {record_count} records (relevance: {relevance:.2f})"
            )

    # Print answer
    if "answer" in response:
        print(f"\n💬 Answer:")
        answer_preview = (
            response["answer"][:500] + "..."
            if len(response["answer"]) > 500
            else response["answer"]
        )
        print(f"  {answer_preview}")

    # Print full response if requested
    if show_full:
        print(f"\n📄 Full Response:")
        print(json.dumps(response, indent=2, default=str))


def test_alerts_pond():
    """Test 1: Query the alerts pond for marine weather advisories"""
    print("\n" + "🌊" * 40)
    print("TEST 1: Marine Weather Alerts")
    print("🌊" * 40)

    query = (
        "What are the current marine weather alerts and advisories for coastal waters?"
    )
    response = invoke_lambda(query)
    print_response(response)

    # Validate response
    if "ponds_queried" in response:
        ponds = [p.get("pond", "").lower() for p in response["ponds_queried"]]
        alerts_queried = any("alert" in p for p in ponds)
        if alerts_queried:
            print("\n✅ PASS: Alerts pond was queried")
        else:
            print("\n⚠️  WARNING: Alerts pond was not queried")

    return response


def test_stations_pond():
    """Test 2: Query the stations pond for observation locations"""
    print("\n" + "📍" * 40)
    print("TEST 2: Weather Station Locations")
    print("📍" * 40)

    query = "Find weather stations and tide gauges near San Francisco Bay"
    response = invoke_lambda(query)
    print_response(response)

    # Validate response
    if "ponds_queried" in response:
        ponds = [p.get("pond", "").lower() for p in response["ponds_queried"]]
        stations_queried = any("station" in p for p in ponds)
        if stations_queried:
            print("\n✅ PASS: Stations pond was queried")
        else:
            print("\n⚠️  WARNING: Stations pond was not queried")

    return response


def test_comprehensive_maritime_route():
    """Test 3: Comprehensive maritime route planning query"""
    print("\n" + "⛵" * 40)
    print("TEST 3: Maritime Route Planning - San Francisco to Los Angeles")
    print("⛵" * 40)

    query = """
    I'm planning a maritime route from San Francisco to Los Angeles.
    What are the current conditions including:
    - Active weather alerts and marine advisories
    - Wave heights and wind conditions from offshore buoys
    - Tide predictions at major ports
    - Water temperatures and currents
    - Weather forecasts along the route
    """

    response = invoke_lambda(query)
    print_response(response, show_full=False)

    # Validate multi-pond response
    if "ponds_queried" in response:
        ponds_queried = [p.get("pond", "").lower() for p in response["ponds_queried"]]
        print(f"\n📋 Validation:")
        print(f"  Ponds queried: {', '.join(ponds_queried)}")

        expected_keywords = ["alert", "atmospheric", "oceanic", "buoy"]
        found_ponds = [
            kw for kw in expected_keywords if any(kw in p for p in ponds_queried)
        ]

        print(f"  Expected pond types: {', '.join(expected_keywords)}")
        print(f"  Found pond types: {', '.join(found_ponds)}")

        if len(found_ponds) >= 3:
            print("\n✅ PASS: Multi-pond maritime query successful")
        else:
            print("\n⚠️  WARNING: Expected more ponds to be queried")

    return response


def test_active_alerts_count():
    """Test 4: Count active marine alerts"""
    print("\n" + "🚨" * 40)
    print("TEST 4: Active Alert Count")
    print("🚨" * 40)

    query = "How many active weather alerts are there currently?"
    response = invoke_lambda(query)
    print_response(response)

    return response


def test_nearest_stations():
    """Test 5: Find nearest observation stations"""
    print("\n" + "🎯" * 40)
    print("TEST 5: Nearest Observation Stations")
    print("🎯" * 40)

    query = "What are the nearest weather observation stations to Miami, Florida?"
    response = invoke_lambda(query)
    print_response(response)

    return response


def test_coastal_conditions():
    """Test 6: Coastal conditions for specific location"""
    print("\n" + "🏖️ " * 40)
    print("TEST 6: Coastal Conditions - San Diego")
    print("🏖️ " * 40)

    query = """
    What are the current coastal conditions for San Diego including:
    - Any weather alerts or advisories
    - Current tide levels
    - Wave heights from nearby buoys
    - Water temperature
    """

    response = invoke_lambda(query)
    print_response(response)

    return response


def run_all_tests():
    """Run all maritime route planning tests"""
    print("\n" + "=" * 80)
    print("NOAA MARITIME ROUTE PLANNING TEST SUITE")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Lambda Function: {LAMBDA_FUNCTION_NAME}")
    print("=" * 80)

    tests = [
        ("Alerts Pond", test_alerts_pond),
        ("Stations Pond", test_stations_pond),
        ("Maritime Route Planning", test_comprehensive_maritime_route),
        ("Active Alerts Count", test_active_alerts_count),
        ("Nearest Stations", test_nearest_stations),
        ("Coastal Conditions", test_coastal_conditions),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            start_time = time.time()
            response = test_func()
            duration = time.time() - start_time

            # Determine if test passed
            passed = (
                response is not None
                and "error" not in response
                and response.get("success", False)
                and ("ponds_queried" in response or "answer" in response)
            )

            results.append(
                {
                    "test": test_name,
                    "passed": passed,
                    "duration": duration,
                }
            )

            time.sleep(1)  # Brief pause between tests

        except Exception as e:
            print(f"\n❌ Test failed with exception: {str(e)}")
            results.append(
                {
                    "test": test_name,
                    "passed": False,
                    "duration": 0,
                    "error": str(e),
                }
            )

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)

    for result in results:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        duration = result["duration"]
        test = result["test"]
        print(f"{status} | {test:<35} | {duration:.2f}s")
        if "error" in result:
            print(f"       Error: {result['error']}")

    print("\n" + "─" * 80)
    print(f"Results: {passed_count}/{total_count} tests passed")
    print("─" * 80)

    # Return exit code
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    try:
        exit_code = run_all_tests()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        sys.exit(1)
