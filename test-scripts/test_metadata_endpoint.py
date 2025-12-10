#!/usr/bin/env python3
"""
Test script for NOAA Data Lake Metadata Endpoint

Tests the dynamic metadata collection functionality of the Lambda function.
"""

import json
import sys
import time
from datetime import datetime

import requests

# Configuration
API_ENDPOINT = "https://5qyjz3ewpk.execute-api.us-east-1.amazonaws.com/prod/query"
PONDS = ["atmospheric", "oceanic", "buoy", "climate", "spatial", "terrestrial"]


def test_all_ponds_metadata():
    """Test fetching metadata for all ponds"""
    print("\n" + "=" * 70)
    print("TEST 1: Fetch All Ponds Metadata")
    print("=" * 70)

    payload = {"action": "get_metadata"}

    print(f"Request: POST {API_ENDPOINT}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    start_time = time.time()

    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        elapsed = time.time() - start_time

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()

            if data.get("success") and data.get("action") == "metadata":
                metadata = data["data"]
                print("\n✅ SUCCESS: Metadata retrieved successfully")

                # Display summary
                summary = metadata.get("summary", {})
                print(f"\nSummary:")
                print(f"  Total Ponds: {summary.get('total_ponds', 0)}")
                print(f"  Active Ponds: {summary.get('active_ponds', 0)}")
                print(f"  Total Files: {summary.get('total_files', 0):,}")
                print(f"  Total Size: {summary.get('total_size_gb', 0):.2f} GB")

                # Display pond details
                print(f"\nPond Details:")
                for pond_name, pond_data in metadata.get("ponds", {}).items():
                    status_icon = "✅" if pond_data.get("status") == "active" else "❌"
                    freshness = pond_data.get("freshness_status", "unknown")
                    freshness_min = pond_data.get("freshness_minutes", "N/A")

                    print(f"  {status_icon} {pond_name.upper()}")
                    print(f"     Files: {pond_data.get('total_files', 0):,}")
                    print(f"     Size: {pond_data.get('total_size_gb', 0):.2f} GB")
                    print(f"     Freshness: {freshness} ({freshness_min} min ago)")
                    print(f"     Layers: {len(pond_data.get('layers', {}))}")

                return True
            else:
                print(f"\n❌ FAILED: Unexpected response format")
                print(f"Response: {json.dumps(data, indent=2)}")
                return False
        else:
            print(f"\n❌ FAILED: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_single_pond_metadata(pond_name):
    """Test fetching metadata for a single pond"""
    print("\n" + "=" * 70)
    print(f"TEST 2: Fetch Single Pond Metadata ({pond_name})")
    print("=" * 70)

    payload = {"action": "get_metadata", "pond": pond_name}

    print(f"Request: POST {API_ENDPOINT}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    start_time = time.time()

    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        elapsed = time.time() - start_time

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()

            if data.get("success") and data.get("action") == "metadata":
                metadata = data["data"]
                pond_data = metadata.get("ponds", {}).get(pond_name)

                if pond_data:
                    print("\n✅ SUCCESS: Single pond metadata retrieved")

                    print(f"\n{pond_name.upper()} Pond:")
                    print(f"  Status: {pond_data.get('status')}")
                    print(f"  Total Files: {pond_data.get('total_files', 0):,}")
                    print(f"  Total Size: {pond_data.get('total_size_gb', 0):.2f} GB")
                    print(
                        f"  Latest Ingestion: {pond_data.get('latest_ingestion', 'N/A')}"
                    )
                    print(
                        f"  Freshness: {pond_data.get('freshness_minutes', 'N/A')} minutes ago"
                    )

                    # Layer breakdown
                    print(f"\n  Layer Breakdown:")
                    for layer, layer_data in pond_data.get("layers", {}).items():
                        print(f"    {layer.upper()}:")
                        print(f"      Files: {layer_data.get('file_count', 0):,}")
                        print(f"      Size: {layer_data.get('size_mb', 0):.2f} MB")
                        print(f"      Latest: {layer_data.get('latest_file', 'N/A')}")

                    return True
                else:
                    print(f"\n❌ FAILED: No data for pond '{pond_name}'")
                    return False
            else:
                print(f"\n❌ FAILED: Unexpected response format")
                print(f"Response: {json.dumps(data, indent=2)[:500]}")
                return False
        else:
            print(f"\n❌ FAILED: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_response_structure():
    """Test that response has correct structure"""
    print("\n" + "=" * 70)
    print("TEST 3: Validate Response Structure")
    print("=" * 70)

    payload = {"action": "get_metadata"}

    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()

            # Check top-level structure
            required_fields = ["success", "action", "data"]
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                print(f"❌ Missing top-level fields: {missing_fields}")
                return False

            metadata = data["data"]

            # Check metadata structure
            metadata_fields = ["collection_timestamp", "bucket", "ponds", "summary"]
            missing_metadata = [f for f in metadata_fields if f not in metadata]

            if missing_metadata:
                print(f"❌ Missing metadata fields: {missing_metadata}")
                return False

            # Check pond structure
            for pond_name, pond_data in metadata.get("ponds", {}).items():
                pond_fields = [
                    "pond_name",
                    "status",
                    "total_files",
                    "total_size_mb",
                    "layers",
                ]
                missing_pond = [f for f in pond_fields if f not in pond_data]

                if missing_pond:
                    print(f"❌ Pond '{pond_name}' missing fields: {missing_pond}")
                    return False

                # Check layer structure
                for layer_name, layer_data in pond_data.get("layers", {}).items():
                    layer_fields = ["file_count", "size_mb"]
                    missing_layer = [f for f in layer_fields if f not in layer_data]

                    if missing_layer:
                        print(
                            f"❌ Layer '{layer_name}' in '{pond_name}' missing fields: {missing_layer}"
                        )
                        return False

            print("✅ SUCCESS: Response structure is valid")
            return True

        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_freshness_calculation():
    """Test that freshness is calculated correctly"""
    print("\n" + "=" * 70)
    print("TEST 4: Validate Freshness Calculation")
    print("=" * 70)

    payload = {"action": "get_metadata"}

    try:
        response = requests.post(
            API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data["data"]

            now = datetime.utcnow()
            collection_time = datetime.fromisoformat(
                metadata["collection_timestamp"].replace("Z", "+00:00")
            )

            # Check collection timestamp is recent (within last minute)
            time_diff = (now - collection_time.replace(tzinfo=None)).total_seconds()
            if time_diff > 60:
                print(f"❌ Collection timestamp too old: {time_diff:.0f} seconds ago")
                return False

            # Check freshness values are reasonable
            for pond_name, pond_data in metadata.get("ponds", {}).items():
                freshness_min = pond_data.get("freshness_minutes")
                if freshness_min is not None:
                    if freshness_min < 0:
                        print(f"❌ Negative freshness for {pond_name}: {freshness_min}")
                        return False
                    if freshness_min > 10080:  # More than a week
                        print(
                            f"⚠️  Warning: {pond_name} data is very stale: {freshness_min} minutes"
                        )

            print("✅ SUCCESS: Freshness calculations are valid")
            return True

        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "#" * 70)
    print("# NOAA Data Lake Metadata Endpoint Tests")
    print("#" * 70)
    print(f"\nAPI Endpoint: {API_ENDPOINT}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    # Test 1: All ponds
    results.append(("All Ponds Metadata", test_all_ponds_metadata()))

    # Test 2: Single pond
    results.append(("Single Pond Metadata", test_single_pond_metadata("atmospheric")))

    # Test 3: Structure validation
    results.append(("Response Structure", test_response_structure()))

    # Test 4: Freshness calculation
    results.append(("Freshness Calculation", test_freshness_calculation()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
