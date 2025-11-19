#!/usr/bin/env python3
"""
Comprehensive Test Suite for All NOAA Data Ponds
Tests ingestion, transformation, and querying across all 6 ponds:
- Oceanic
- Atmospheric
- Climate
- Spatial
- Terrestrial
- Buoy

Usage:
    python3 test_all_ponds.py --env dev
    python3 test_all_ponds.py --env dev --pond oceanic
    python3 test_all_ponds.py --env dev --skip-ingestion
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import boto3
import requests

# AWS Clients
s3_client = boto3.client("s3", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")

# Test Configuration
TEST_TIMEOUT = 300  # 5 minutes
POLL_INTERVAL = 5  # seconds

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class TestResult:
    """Track test results"""

    def __init__(self, pond: str, test_name: str):
        self.pond = pond
        self.test_name = test_name
        self.passed = False
        self.message = ""
        self.duration = 0.0
        self.data_count = 0
        self.error = None

    def __repr__(self):
        status = f"{GREEN}PASS{RESET}" if self.passed else f"{RED}FAIL{RESET}"
        return f"[{status}] {self.pond}.{self.test_name}: {self.message}"


class PondTester:
    """Base class for pond testing"""

    def __init__(self, env: str, bucket: str, athena_results_bucket: str):
        self.env = env
        self.bucket = bucket
        self.athena_results_bucket = athena_results_bucket
        self.gold_db = f"noaa_gold_{env}"
        self.results = []

    def add_result(self, result: TestResult):
        """Add test result"""
        self.results.append(result)
        print(f"  {result}")

    def test_s3_bronze_data(
        self, pond: str, prefix: str, min_files: int = 1
    ) -> TestResult:
        """Test that Bronze layer has data"""
        result = TestResult(pond, "bronze_data_exists")
        start_time = time.time()

        try:
            # Check for recent data (last 7 days)
            date_prefixes = []
            for days_ago in range(7):
                date = (datetime.utcnow() - timedelta(days=days_ago)).strftime(
                    "%Y-%m-%d"
                )
                date_prefixes.append(f"bronze/{pond}/{prefix}/date={date}/")

            total_files = 0
            for date_prefix in date_prefixes:
                try:
                    response = s3_client.list_objects_v2(
                        Bucket=self.bucket, Prefix=date_prefix, MaxKeys=100
                    )
                    if "Contents" in response:
                        total_files += len(response["Contents"])
                except Exception:
                    continue

            result.duration = time.time() - start_time
            result.data_count = total_files

            if total_files >= min_files:
                result.passed = True
                result.message = f"Found {total_files} files in Bronze layer"
            else:
                result.message = (
                    f"Expected at least {min_files} files, found {total_files}"
                )

        except Exception as e:
            result.error = str(e)
            result.message = f"Error checking Bronze layer: {e}"
            result.duration = time.time() - start_time

        return result

    def test_s3_gold_data(
        self, pond: str, prefix: str, min_files: int = 1
    ) -> TestResult:
        """Test that Gold layer has data"""
        result = TestResult(pond, "gold_data_exists")
        start_time = time.time()

        try:
            # Check for recent data (last 7 days)
            date_prefixes = []
            for days_ago in range(7):
                date = (datetime.utcnow() - timedelta(days=days_ago)).strftime(
                    "%Y-%m-%d"
                )
                date_prefixes.append(f"gold/{pond}/{prefix}/date={date}/")

            total_files = 0
            for date_prefix in date_prefixes:
                try:
                    response = s3_client.list_objects_v2(
                        Bucket=self.bucket, Prefix=date_prefix, MaxKeys=100
                    )
                    if "Contents" in response:
                        total_files += len(response["Contents"])
                except Exception:
                    continue

            result.duration = time.time() - start_time
            result.data_count = total_files

            if total_files >= min_files:
                result.passed = True
                result.message = f"Found {total_files} files in Gold layer"
            else:
                result.message = (
                    f"Expected at least {min_files} files, found {total_files}"
                )

        except Exception as e:
            result.error = str(e)
            result.message = f"Error checking Gold layer: {e}"
            result.duration = time.time() - start_time

        return result

    def test_athena_table(
        self, table_name: str, expected_columns: List[str]
    ) -> TestResult:
        """Test that Athena table exists and has expected structure"""
        result = TestResult(table_name.split("_")[0], f"athena_table_{table_name}")
        start_time = time.time()

        try:
            query = f"DESCRIBE {self.gold_db}.{table_name}"
            query_id = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": self.gold_db},
                ResultConfiguration={
                    "OutputLocation": f"s3://{self.athena_results_bucket}/tests/"
                },
            )["QueryExecutionId"]

            # Wait for query to complete
            status = self._wait_for_query(query_id)

            if status == "SUCCEEDED":
                # Get results
                response = athena_client.get_query_results(QueryExecutionId=query_id)
                columns = [
                    row["Data"][0]["VarCharValue"]
                    for row in response["ResultSet"]["Rows"][1:]
                ]

                missing_columns = [
                    col for col in expected_columns if col not in columns
                ]

                result.duration = time.time() - start_time
                result.data_count = len(columns)

                if not missing_columns:
                    result.passed = True
                    result.message = (
                        f"Table has all {len(expected_columns)} expected columns"
                    )
                else:
                    result.message = f"Missing columns: {', '.join(missing_columns)}"
            else:
                result.message = f"Query failed with status: {status}"

        except Exception as e:
            result.error = str(e)
            result.message = f"Error checking table: {e}"
            result.duration = time.time() - start_time

        return result

    def test_athena_query_data(
        self, table_name: str, min_rows: int = 1, max_days_old: int = 7
    ) -> TestResult:
        """Test that table has queryable data"""
        result = TestResult(table_name.split("_")[0], f"athena_query_{table_name}")
        start_time = time.time()

        try:
            # Query recent data
            query = f"""
            SELECT COUNT(*) as row_count
            FROM {self.gold_db}.{table_name}
            WHERE date >= date_format(current_date - interval '{max_days_old}' day, '%Y-%m-%d')
            """

            query_id = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": self.gold_db},
                ResultConfiguration={
                    "OutputLocation": f"s3://{self.athena_results_bucket}/tests/"
                },
            )["QueryExecutionId"]

            status = self._wait_for_query(query_id)

            if status == "SUCCEEDED":
                response = athena_client.get_query_results(QueryExecutionId=query_id)
                if len(response["ResultSet"]["Rows"]) > 1:
                    row_count = int(
                        response["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"]
                    )

                    result.duration = time.time() - start_time
                    result.data_count = row_count

                    if row_count >= min_rows:
                        result.passed = True
                        result.message = (
                            f"Found {row_count} rows in last {max_days_old} days"
                        )
                    else:
                        result.message = (
                            f"Expected at least {min_rows} rows, found {row_count}"
                        )
                else:
                    result.message = "No data returned from query"
            else:
                result.message = f"Query failed with status: {status}"

        except Exception as e:
            result.error = str(e)
            result.message = f"Error querying table: {e}"
            result.duration = time.time() - start_time

        return result

    def _wait_for_query(self, query_id: str, timeout: int = 60) -> str:
        """Wait for Athena query to complete"""
        start = time.time()
        while time.time() - start < timeout:
            response = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = response["QueryExecution"]["Status"]["State"]
            if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                return status
            time.sleep(2)
        return "TIMEOUT"


class OceanicPondTester(PondTester):
    """Test Oceanic Pond"""

    def run_tests(self):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Oceanic Pond{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")

        # Test Bronze layer
        self.add_result(self.test_s3_bronze_data("oceanic", "buoys", min_files=1))
        self.add_result(self.test_s3_bronze_data("oceanic", "tides", min_files=1))

        # Test Gold layer
        self.add_result(self.test_s3_gold_data("oceanic", "buoys", min_files=1))
        self.add_result(self.test_s3_gold_data("oceanic", "tides", min_files=1))

        # Test Athena tables
        self.add_result(
            self.test_athena_table(
                "oceanic_buoys",
                ["station_id", "latitude", "longitude", "wave_height", "temperature"],
            )
        )
        self.add_result(
            self.test_athena_table(
                "oceanic_tides", ["station_id", "station_name", "water_level"]
            )
        )

        # Test data queries
        self.add_result(self.test_athena_query_data("oceanic_buoys", min_rows=10))
        self.add_result(self.test_athena_query_data("oceanic_tides", min_rows=10))


class AtmosphericPondTester(PondTester):
    """Test Atmospheric Pond"""

    def run_tests(self):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Atmospheric Pond{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")

        # Test Bronze layer
        self.add_result(self.test_s3_bronze_data("atmospheric", "alerts", min_files=1))
        self.add_result(
            self.test_s3_bronze_data("atmospheric", "forecasts", min_files=5)
        )

        # Test Gold layer
        self.add_result(self.test_s3_gold_data("atmospheric", "alerts", min_files=1))
        self.add_result(self.test_s3_gold_data("atmospheric", "forecasts", min_files=5))

        # Test Athena tables
        self.add_result(
            self.test_athena_table(
                "atmospheric_alerts", ["timestamp", "total_alerts", "alert_summary"]
            )
        )
        self.add_result(
            self.test_athena_table(
                "atmospheric_forecasts",
                ["location_name", "state", "temperature", "forecast_high_temp"],
            )
        )

        # Test data queries
        self.add_result(self.test_athena_query_data("atmospheric_alerts", min_rows=1))
        self.add_result(
            self.test_athena_query_data("atmospheric_forecasts", min_rows=5)
        )


class ClimatePondTester(PondTester):
    """Test Climate Pond"""

    def run_tests(self):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Climate Pond{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")

        # Test Bronze layer
        self.add_result(self.test_s3_bronze_data("climate", "daily", min_files=1))
        self.add_result(self.test_s3_bronze_data("climate", "normals", min_files=1))

        # Test Gold layer
        self.add_result(self.test_s3_gold_data("climate", "daily_summary", min_files=1))
        self.add_result(
            self.test_s3_gold_data("climate", "station_summary", min_files=1)
        )

        # Test Athena tables
        self.add_result(
            self.test_athena_table(
                "climate_daily",
                ["station_id", "temperature_max", "temperature_min", "precipitation"],
            )
        )

        # Test data queries
        self.add_result(self.test_athena_query_data("climate_daily", min_rows=5))


class SpatialPondTester(PondTester):
    """Test Spatial Pond"""

    def run_tests(self):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Spatial Pond{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")

        # Test Bronze layer
        self.add_result(self.test_s3_bronze_data("spatial", "radar", min_files=1))
        self.add_result(self.test_s3_bronze_data("spatial", "satellite", min_files=1))

        # Test Gold layer
        self.add_result(self.test_s3_gold_data("spatial", "radar_summary", min_files=1))
        self.add_result(
            self.test_s3_gold_data("spatial", "satellite_summary", min_files=1)
        )


class TerrestrialPondTester(PondTester):
    """Test Terrestrial Pond"""

    def run_tests(self):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Terrestrial Pond{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")

        # Test Bronze layer
        self.add_result(
            self.test_s3_bronze_data("terrestrial", "river_gauges", min_files=1)
        )
        self.add_result(
            self.test_s3_bronze_data("terrestrial", "precipitation", min_files=1)
        )

        # Test Gold layer
        self.add_result(
            self.test_s3_gold_data("terrestrial", "river_gauge_summary", min_files=1)
        )


class BuoyPondTester(PondTester):
    """Test Buoy Pond (part of Oceanic)"""

    def run_tests(self):
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Buoy Pond{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")

        # Test Bronze layer
        self.add_result(self.test_s3_bronze_data("oceanic", "buoys", min_files=5))
        self.add_result(self.test_s3_bronze_data("oceanic", "realtime", min_files=1))

        # Test Gold layer
        self.add_result(self.test_s3_gold_data("oceanic", "buoys", min_files=5))


def test_federated_query(
    env: str, bucket: str, athena_results_bucket: str
) -> TestResult:
    """Test federated query across multiple ponds"""
    result = TestResult("federated", "cross_pond_query")
    start_time = time.time()
    gold_db = f"noaa_gold_{env}"

    try:
        # Query that joins data from multiple ponds
        query = f"""
        SELECT
            'atmospheric' as pond_type,
            COUNT(*) as record_count
        FROM {gold_db}.atmospheric_forecasts
        WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d')

        UNION ALL

        SELECT
            'oceanic' as pond_type,
            COUNT(*) as record_count
        FROM {gold_db}.oceanic_buoys
        WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d')

        UNION ALL

        SELECT
            'climate' as pond_type,
            COUNT(*) as record_count
        FROM {gold_db}.climate_daily
        WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d')
        """

        query_id = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": gold_db},
            ResultConfiguration={
                "OutputLocation": f"s3://{athena_results_bucket}/tests/"
            },
        )["QueryExecutionId"]

        # Wait for query
        timeout = 60
        start_wait = time.time()
        while time.time() - start_wait < timeout:
            response = athena_client.get_query_execution(QueryExecutionId=query_id)
            status = response["QueryExecution"]["Status"]["State"]
            if status == "SUCCEEDED":
                break
            elif status in ["FAILED", "CANCELLED"]:
                result.message = f"Federated query failed: {status}"
                return result
            time.sleep(2)

        if status == "SUCCEEDED":
            response = athena_client.get_query_results(QueryExecutionId=query_id)
            rows = response["ResultSet"]["Rows"][1:]  # Skip header

            result.duration = time.time() - start_time
            result.data_count = len(rows)

            if len(rows) >= 3:  # Should have results from all 3 ponds
                result.passed = True
                result.message = f"Successfully queried {len(rows)} ponds"
            else:
                result.message = f"Expected 3 ponds, got {len(rows)}"
        else:
            result.message = "Query timeout"

    except Exception as e:
        result.error = str(e)
        result.message = f"Error in federated query: {e}"
        result.duration = time.time() - start_time

    return result


def generate_report(all_results: List[TestResult], output_file: str):
    """Generate comprehensive test report"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Calculate statistics
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r.passed)
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    # Group by pond
    ponds = {}
    for result in all_results:
        if result.pond not in ponds:
            ponds[result.pond] = {"passed": 0, "failed": 0, "tests": []}
        if result.passed:
            ponds[result.pond]["passed"] += 1
        else:
            ponds[result.pond]["failed"] += 1
        ponds[result.pond]["tests"].append(result)

    # Generate report
    report = f"""# NOAA Federated Data Lake - Comprehensive Test Report

**Generated:** {timestamp}

## Executive Summary

- **Total Tests:** {total_tests}
- **Passed:** {GREEN}{passed_tests}{RESET} ({pass_rate:.1f}%)
- **Failed:** {RED}{failed_tests}{RESET}
- **Overall Status:** {"✅ HEALTHY" if pass_rate >= 80 else "⚠️ ISSUES DETECTED" if pass_rate >= 60 else "❌ CRITICAL"}

## Pond-by-Pond Results

"""

    for pond, stats in sorted(ponds.items()):
        pond_pass_rate = (
            stats["passed"] / (stats["passed"] + stats["failed"]) * 100
            if (stats["passed"] + stats["failed"]) > 0
            else 0
        )
        report += f"""
### {pond.upper()} Pond

- **Tests:** {stats["passed"] + stats["failed"]}
- **Passed:** {stats["passed"]}
- **Failed:** {stats["failed"]}
- **Pass Rate:** {pond_pass_rate:.1f}%

"""

        for test in stats["tests"]:
            status = "✅" if test.passed else "❌"
            report += f"{status} **{test.test_name}**: {test.message} ({test.duration:.2f}s)\n"

        report += "\n"

    # Failed tests detail
    failed = [r for r in all_results if not r.passed]
    if failed:
        report += "## Failed Tests Detail\n\n"
        for result in failed:
            report += f"""
### {result.pond}.{result.test_name}

- **Message:** {result.message}
- **Duration:** {result.duration:.2f}s
"""
            if result.error:
                report += f"- **Error:** `{result.error}`\n"
            report += "\n"

    # Recommendations
    report += """
## Recommendations

"""
    if pass_rate >= 90:
        report += "- ✅ All systems are operating within normal parameters\n"
        report += "- Continue regular monitoring and maintenance\n"
    elif pass_rate >= 70:
        report += "- ⚠️ Some issues detected, but system is functional\n"
        report += "- Review failed tests and address issues\n"
    else:
        report += "- ❌ Critical issues detected\n"
        report += "- Immediate attention required\n"
        report += "- Review ingestion pipelines and data sources\n"

    report += "\n---\n\n*End of Report*\n"

    # Write to file
    with open(output_file, "w") as f:
        # Remove color codes for file output
        clean_report = (
            report.replace(GREEN, "")
            .replace(RED, "")
            .replace(YELLOW, "")
            .replace(BLUE, "")
            .replace(RESET, "")
        )
        f.write(clean_report)

    print(f"\n📄 Report saved to: {output_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Test all NOAA data ponds")
    parser.add_argument("--env", default="dev", help="Environment (dev/prod)")
    parser.add_argument(
        "--pond",
        choices=[
            "oceanic",
            "atmospheric",
            "climate",
            "spatial",
            "terrestrial",
            "buoy",
            "all",
        ],
        default="all",
        help="Specific pond to test",
    )
    parser.add_argument(
        "--skip-ingestion", action="store_true", help="Skip ingestion tests"
    )
    parser.add_argument("--output", default="logs/test_report.md", help="Output file")
    args = parser.parse_args()

    env = args.env
    bucket = f"noaa-federated-lake-899626030376-{env}"
    athena_results_bucket = f"noaa-athena-results-899626030376-{env}"

    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}NOAA Federated Data Lake - Comprehensive Testing{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}")
    print(f"Environment: {env}")
    print(f"Bucket: {bucket}")
    print(f"Testing: {args.pond}")
    print(f"{GREEN}{'=' * 60}{RESET}\n")

    all_results = []

    # Run tests for each pond
    ponds_to_test = (
        ["oceanic", "atmospheric", "climate", "spatial", "terrestrial", "buoy"]
        if args.pond == "all"
        else [args.pond]
    )

    for pond in ponds_to_test:
        if pond == "oceanic":
            tester = OceanicPondTester(env, bucket, athena_results_bucket)
        elif pond == "atmospheric":
            tester = AtmosphericPondTester(env, bucket, athena_results_bucket)
        elif pond == "climate":
            tester = ClimatePondTester(env, bucket, athena_results_bucket)
        elif pond == "spatial":
            tester = SpatialPondTester(env, bucket, athena_results_bucket)
        elif pond == "terrestrial":
            tester = TerrestrialPondTester(env, bucket, athena_results_bucket)
        elif pond == "buoy":
            tester = BuoyPondTester(env, bucket, athena_results_bucket)
        else:
            continue

        tester.run_tests()
        all_results.extend(tester.results)

    # Test federated queries
    if args.pond == "all":
        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}Testing Federated Queries{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}\n")
        fed_result = test_federated_query(env, bucket, athena_results_bucket)
        print(f"  {fed_result}")
        all_results.append(fed_result)

    # Generate report
    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}Generating Report{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}\n")

    report = generate_report(all_results, args.output)

    # Print summary
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}Test Summary{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}")
    print(f"Total Tests: {total}")
    print(f"Passed: {GREEN}{passed}{RESET}")
    print(f"Failed: {RED}{total - passed}{RESET}")
    print(f"Pass Rate: {passed / total * 100:.1f}%")
    print(f"{GREEN}{'=' * 60}{RESET}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
