#!/usr/bin/env python3
"""
NOAA Federated Data Lake - Comprehensive AWS Analysis and Diagnostic Report

This script performs a complete audit of:
1. All Lambda functions and their execution status
2. S3 data consumption across all medallion layers (Bronze, Silver, Gold)
3. Data ingestion endpoints and their activity
4. Medallion transformation pipeline status
5. AI query handler functionality
6. CloudWatch logs for errors and performance issues

Generates a detailed diagnostic report with:
- Endpoint consumption analysis
- Data profiles per pond
- Medallion transformation metrics
- AI interpretation test results
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import boto3
import botocore

# AWS Clients
lambda_client = boto3.client("lambda", region_name="us-east-1")
s3_client = boto3.client("s3", region_name="us-east-1")
logs_client = boto3.client("logs", region_name="us-east-1")
athena_client = boto3.client("athena", region_name="us-east-1")
cloudwatch_client = boto3.client("cloudwatch", region_name="us-east-1")

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Data Ponds Configuration
PONDS = {
    "atmospheric": {
        "lambda": "NOAAIngestAtmospheric-dev",
        "endpoints": [
            "https://api.weather.gov/alerts",
            "https://api.weather.gov/alerts/active",
            "https://api.weather.gov/gridpoints",
            "https://api.weather.gov/stations",
            "https://api.weather.gov/points",
        ],
        "s3_paths": {
            "bronze": "bronze/atmospheric/",
            "silver": "silver/atmospheric/",
            "gold": "gold/atmospheric/",
        },
        "data_types": ["observations", "alerts", "forecasts", "stations"],
    },
    "oceanic": {
        "lambda": "NOAAIngestOceanic-dev",
        "endpoints": [
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
        ],
        "s3_paths": {
            "bronze": "bronze/oceanic/",
            "silver": "silver/oceanic/",
            "gold": "gold/oceanic/",
        },
        "data_types": ["water_level", "water_temperature", "wind", "currents"],
    },
    "buoy": {
        "lambda": "NOAAIngestBuoy-dev",
        "endpoints": [
            "https://www.ndbc.noaa.gov/data/realtime2/",
            "https://www.ndbc.noaa.gov/data/stations/",
        ],
        "s3_paths": {
            "bronze": "bronze/buoy/",
            "silver": "silver/buoy/",
            "gold": "gold/buoy/",
        },
        "data_types": ["metadata", "measurements", "wave_data"],
    },
    "climate": {
        "lambda": "NOAAIngestClimate-dev",
        "endpoints": [
            "https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets",
            "https://www.ncdc.noaa.gov/cdo-web/api/v2/data",
            "https://www.ncdc.noaa.gov/cdo-web/api/v2/stations",
        ],
        "s3_paths": {
            "bronze": "bronze/climate/",
            "silver": "silver/climate/",
            "gold": "gold/climate/",
        },
        "data_types": ["daily", "monthly", "normals"],
    },
    "terrestrial": {
        "lambda": "NOAAIngestTerrestrial-dev",
        "endpoints": [
            "https://waterservices.usgs.gov/nwis/site/",
            "https://waterservices.usgs.gov/nwis/dv/",
            "https://waterservices.usgs.gov/nwis/iv/",
        ],
        "s3_paths": {
            "bronze": "bronze/terrestrial/",
            "silver": "silver/terrestrial/",
            "gold": "gold/terrestrial/",
        },
        "data_types": ["river_flow", "gauge_height", "precipitation"],
    },
    "spatial": {
        "lambda": "NOAAIngestSpatial-dev",
        "endpoints": [
            "https://api.weather.gov/radar/servers",
            "https://api.weather.gov/radar/stations",
        ],
        "s3_paths": {
            "bronze": "bronze/spatial/",
            "silver": "silver/spatial/",
            "gold": "gold/spatial/",
        },
        "data_types": ["radar_metadata", "satellite_products"],
    },
}


class AWSAnalyzer:
    """Main analyzer class for NOAA data lake"""

    def __init__(self, env: str = "dev"):
        self.env = env
        self.report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": env,
            "lambdas": {},
            "s3": {},
            "medallion": {},
            "endpoints": {},
            "ai_handler": {},
            "summary": {},
        }
        self.s3_bucket = self._get_s3_bucket()

    def _get_s3_bucket(self) -> str:
        """Get the S3 bucket name for this environment"""
        try:
            # Try to find the bucket
            response = s3_client.list_buckets()
            for bucket in response["Buckets"]:
                if f"noaa-federated-lake" in bucket["Name"] and self.env in bucket["Name"]:
                    return bucket["Name"]
            # Fallback to constructed name
            account_id = boto3.client("sts").get_caller_identity()["Account"]
            return f"noaa-federated-lake-{account_id}-{self.env}"
        except Exception as e:
            print(f"{RED}Error getting S3 bucket: {e}{RESET}")
            return None

    def analyze_lambda_functions(self) -> Dict:
        """Analyze all Lambda functions and their execution metrics"""
        print(f"\n{CYAN}=== ANALYZING LAMBDA FUNCTIONS ==={RESET}")

        lambda_data = {"functions": {}, "total_invocations": 0, "total_errors": 0}

        for pond, config in PONDS.items():
            lambda_name = config["lambda"]
            print(f"\n{BLUE}Checking: {lambda_name}{RESET}")

            try:
                # Get function details
                func_response = lambda_client.get_function(FunctionName=lambda_name)
                func_config = func_response["Configuration"]

                # Get function metrics
                metrics = self._get_lambda_metrics(lambda_name)

                lambda_data["functions"][pond] = {
                    "name": lambda_name,
                    "status": "✓ Active" if func_config["State"] == "Active" else "✗ Inactive",
                    "runtime": func_config.get("Runtime", "N/A"),
                    "memory": func_config.get("MemorySize", "N/A"),
                    "timeout": func_config.get("Timeout", "N/A"),
                    "last_modified": func_config.get("LastModified", "N/A"),
                    "environment_vars": func_config.get("Environment", {}).get("Variables", {}),
                    "metrics": metrics,
                }

                print(f"  Status: {lambda_data['functions'][pond]['status']}")
                print(f"  Memory: {func_config.get('MemorySize', 'N/A')} MB")
                print(f"  Runtime: {func_config.get('Runtime', 'N/A')}")
                print(f"  Invocations (24h): {metrics.get('invocations', 0)}")
                print(f"  Errors (24h): {metrics.get('errors', 0)}")
                print(f"  Avg Duration: {metrics.get('avg_duration', 0):.2f}ms")

                lambda_data["total_invocations"] += metrics.get("invocations", 0)
                lambda_data["total_errors"] += metrics.get("errors", 0)

            except lambda_client.exceptions.ResourceNotFoundException:
                print(f"  {RED}✗ Function not found: {lambda_name}{RESET}")
                lambda_data["functions"][pond] = {"status": "✗ Not found"}
            except Exception as e:
                print(f"  {RED}✗ Error: {str(e)}{RESET}")
                lambda_data["functions"][pond] = {"status": f"✗ Error: {str(e)}"}

        self.report["lambdas"] = lambda_data
        return lambda_data

    def _get_lambda_metrics(self, function_name: str, hours: int = 24) -> Dict:
        """Get CloudWatch metrics for a Lambda function"""
        metrics = {
            "invocations": 0,
            "errors": 0,
            "avg_duration": 0,
            "max_duration": 0,
        }

        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

            # Get invocations
            response = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName="Invocations",
                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=["Sum"],
            )
            metrics["invocations"] = sum(dp["Sum"] for dp in response["Datapoints"])

            # Get errors
            response = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName="Errors",
                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=["Sum"],
            )
            metrics["errors"] = sum(dp["Sum"] for dp in response["Datapoints"])

            # Get duration
            response = cloudwatch_client.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName="Duration",
                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=["Average", "Maximum"],
            )
            if response["Datapoints"]:
                metrics["avg_duration"] = sum(dp.get("Average", 0) for dp in response["Datapoints"]) / len(
                    response["Datapoints"]
                )
                metrics["max_duration"] = max(dp.get("Maximum", 0) for dp in response["Datapoints"])

        except Exception as e:
            print(f"    {YELLOW}Warning: Could not get metrics - {str(e)}{RESET}")

        return metrics

    def analyze_s3_consumption(self) -> Dict:
        """Analyze S3 data consumption across all medallion layers"""
        print(f"\n{CYAN}=== ANALYZING S3 DATA CONSUMPTION ==={RESET}")

        s3_data = {
            "bucket": self.s3_bucket,
            "layers": {"bronze": {}, "silver": {}, "gold": {}},
            "total_objects": 0,
            "total_size_gb": 0,
        }

        if not self.s3_bucket:
            print(f"{RED}S3 bucket not found{RESET}")
            return s3_data

        print(f"Bucket: {self.s3_bucket}")

        try:
            # List all objects
            paginator = s3_client.get_paginator("list_objects_v2")

            for layer in ["bronze", "silver", "gold"]:
                print(f"\n{BLUE}Layer: {layer.upper()}{RESET}")
                layer_data = {"ponds": {}, "total_objects": 0, "total_size_bytes": 0, "last_modified": None}

                for pond, config in PONDS.items():
                    prefix = config["s3_paths"].get(layer, f"{layer}/{pond}/")
                    pond_data = {
                        "objects": 0,
                        "size_bytes": 0,
                        "size_mb": 0,
                        "last_modified": None,
                        "data_types": [],
                    }

                    try:
                        pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix)

                        for page in pages:
                            if "Contents" in page:
                                for obj in page["Contents"]:
                                    pond_data["objects"] += 1
                                    pond_data["size_bytes"] += obj["Size"]
                                    if (
                                        not pond_data["last_modified"]
                                        or obj["LastModified"] > pond_data["last_modified"]
                                    ):
                                        pond_data["last_modified"] = obj["LastModified"].isoformat()

                    except Exception as e:
                        print(f"  {YELLOW}Error reading prefix {prefix}: {str(e)}{RESET}")

                    if pond_data["objects"] > 0:
                        pond_data["size_mb"] = pond_data["size_bytes"] / (1024 * 1024)
                        layer_data["ponds"][pond] = pond_data
                        layer_data["total_objects"] += pond_data["objects"]
                        layer_data["total_size_bytes"] += pond_data["size_bytes"]

                        print(
                            f"  {pond:12} → {pond_data['objects']:6} objects, "
                            f"{pond_data['size_mb']:10.2f} MB, last: {pond_data['last_modified']}"
                        )

                layer_data["total_size_mb"] = layer_data["total_size_bytes"] / (1024 * 1024)
                layer_data["total_size_gb"] = layer_data["total_size_mb"] / 1024
                s3_data["layers"][layer] = layer_data

                print(
                    f"  {BOLD}Layer Total{RESET}: {layer_data['total_objects']} objects, "
                    f"{layer_data['total_size_gb']:.2f} GB"
                )

                s3_data["total_objects"] += layer_data["total_objects"]
                s3_data["total_size_gb"] += layer_data["total_size_gb"]

        except Exception as e:
            print(f"{RED}Error analyzing S3: {str(e)}{RESET}")

        self.report["s3"] = s3_data
        return s3_data

    def analyze_medallion_transformation(self) -> Dict:
        """Analyze medallion transformation pipeline"""
        print(f"\n{CYAN}=== ANALYZING MEDALLION TRANSFORMATION ==={RESET}")

        medallion_data = {
            "ponds": {},
            "transformation_ratios": {},
            "data_quality": {},
        }

        s3_layers = self.report.get("s3", {}).get("layers", {})

        for pond in PONDS.keys():
            print(f"\n{BLUE}Pond: {pond.upper()}{RESET}")

            bronze_size = s3_layers.get("bronze", {}).get("ponds", {}).get(pond, {}).get("size_mb", 0)
            silver_size = s3_layers.get("silver", {}).get("ponds", {}).get(pond, {}).get("size_mb", 0)
            gold_size = s3_layers.get("gold", {}).get("ponds", {}).get(pond, {}).get("size_mb", 0)

            bronze_objs = s3_layers.get("bronze", {}).get("ponds", {}).get(pond, {}).get("objects", 0)
            silver_objs = s3_layers.get("silver", {}).get("ponds", {}).get(pond, {}).get("objects", 0)
            gold_objs = s3_layers.get("gold", {}).get("ponds", {}).get(pond, {}).get("objects", 0)

            medallion_data["ponds"][pond] = {
                "bronze_mb": bronze_size,
                "silver_mb": silver_size,
                "gold_mb": gold_size,
                "bronze_objects": bronze_objs,
                "silver_objects": silver_objs,
                "gold_objects": gold_objs,
            }

            print(f"  Bronze (raw):      {bronze_size:10.2f} MB, {bronze_objs:6} objects")
            print(f"  Silver (processed): {silver_size:10.2f} MB, {silver_objs:6} objects")
            print(f"  Gold (analytics):  {gold_size:10.2f} MB, {gold_objs:6} objects")

            # Calculate ratios
            if bronze_size > 0:
                silver_ratio = silver_size / bronze_size
                gold_ratio = gold_size / silver_size if silver_size > 0 else 0
                total_compression = gold_size / bronze_size if bronze_size > 0 else 0

                medallion_data["transformation_ratios"][pond] = {
                    "bronze_to_silver": f"{silver_ratio:.2%}",
                    "silver_to_gold": f"{gold_ratio:.2%}",
                    "total_compression": f"{total_compression:.2%}",
                }

                print(f"  Bronze → Silver: {silver_ratio:.2%}")
                print(f"  Silver → Gold: {gold_ratio:.2%}")
                print(f"  Total compression: {total_compression:.2%}")

        self.report["medallion"] = medallion_data
        return medallion_data

    def analyze_endpoints_consumption(self) -> Dict:
        """Analyze which endpoints are being consumed"""
        print(f"\n{CYAN}=== ANALYZING ENDPOINT CONSUMPTION ==={RESET}")

        endpoints_data = {"ponds": {}, "active_endpoints": 0, "inactive_endpoints": 0}

        for pond, config in PONDS.items():
            print(f"\n{BLUE}Pond: {pond.upper()}{RESET}")

            lambda_name = config["lambda"]
            endpoints_list = config.get("endpoints", [])

            # Get Lambda logs to check for endpoint calls
            log_group = f"/aws/lambda/{lambda_name}"
            endpoint_calls = self._check_endpoint_calls_in_logs(log_group, endpoints_list)

            endpoints_data["ponds"][pond] = {
                "lambda": lambda_name,
                "configured_endpoints": len(endpoints_list),
                "active_endpoints": sum(1 for e in endpoint_calls.values() if e > 0),
                "endpoint_calls": endpoint_calls,
            }

            endpoints_data["active_endpoints"] += sum(1 for e in endpoint_calls.values() if e > 0)
            endpoints_data["inactive_endpoints"] += sum(1 for e in endpoint_calls.values() if e == 0)

            print(f"  Configured: {len(endpoints_list)} endpoints")
            print(f"  Active: {sum(1 for e in endpoint_calls.values() if e > 0)} (consuming data)")
            print(f"  Inactive: {sum(1 for e in endpoint_calls.values() if e == 0)}")

            for endpoint, count in endpoint_calls.items():
                status = f"{GREEN}✓{RESET}" if count > 0 else f"{RED}✗{RESET}"
                print(f"    {status} {endpoint[:60]:60} → {count} calls")

        self.report["endpoints"] = endpoints_data
        return endpoints_data

    def _check_endpoint_calls_in_logs(self, log_group: str, endpoints: List[str]) -> Dict:
        """Check CloudWatch logs for endpoint calls"""
        endpoint_calls = {endpoint[:80]: 0 for endpoint in endpoints}

        try:
            end_time = int(time.time() * 1000)
            start_time = int((time.time() - 86400) * 1000)  # Last 24 hours

            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_time,
                endTime=end_time,
                limit=1000,
            )

            if "events" in response:
                log_text = " ".join(event["message"] for event in response["events"])

                for endpoint in endpoints:
                    # Extract domain/path for matching
                    base_endpoint = endpoint.split("?")[0].replace("{", "").replace("}", "")
                    domain = base_endpoint.split("//")[-1].split("/")[0]

                    if domain in log_text or base_endpoint in log_text:
                        # Count occurrences
                        count = log_text.count(domain)
                        endpoint_calls[endpoint[:80]] = count

        except logs_client.exceptions.ResourceNotFoundException:
            print(f"    {YELLOW}Log group not found: {log_group}{RESET}")
        except Exception as e:
            print(f"    {YELLOW}Warning: Could not read logs - {str(e)}{RESET}")

        return endpoint_calls

    def analyze_ai_query_handler(self) -> Dict:
        """Test the AI query handler functionality"""
        print(f"\n{CYAN}=== ANALYZING AI QUERY HANDLER ==={RESET}")

        ai_data = {"function_name": "noaa-ai-query-dev", "status": "unknown", "tests": {}}

        try:
            # Get AI query handler function
            func_response = lambda_client.get_function(FunctionName="noaa-ai-query-dev")
            func_config = func_response["Configuration"]

            ai_data["status"] = "✓ Active" if func_config["State"] == "Active" else "✗ Inactive"
            ai_data["runtime"] = func_config.get("Runtime")
            ai_data["memory"] = func_config.get("MemorySize")

            print(f"Function: {func_config['FunctionName']}")
            print(f"Status: {ai_data['status']}")
            print(f"Runtime: {func_config.get('Runtime')}")
            print(f"Memory: {func_config.get('MemorySize')} MB")

            # Test with sample query
            print(f"\n{BLUE}Testing AI Query Handler...{RESET}")
            test_queries = [
                {"query": "What are the current weather conditions in Miami?", "ponds": ["atmospheric"]},
                {"query": "Show me water levels along the East Coast", "ponds": ["oceanic"]},
                {"query": "Are there any weather alerts in the Gulf of Mexico?", "ponds": ["atmospheric"]},
            ]

            for i, test_query in enumerate(test_queries):
                print(f"\nTest {i + 1}: {test_query['query'][:50]}...")

                try:
                    response = lambda_client.invoke(
                        FunctionName="noaa-ai-query-dev",
                        InvocationType="RequestResponse",
                        Payload=json.dumps(test_query),
                    )

                    if response["StatusCode"] == 200:
                        payload = json.loads(response.get("Payload", "{}").read())
                        ai_data["tests"][f"test_{i+1}"] = {
                            "status": "✓ Success",
                            "status_code": response["StatusCode"],
                            "response_length": len(str(payload)),
                        }
                        print(f"  {GREEN}✓ Success{RESET} - Response length: {len(str(payload))} chars")
                        if isinstance(payload, dict) and "body" in payload:
                            try:
                                body = json.loads(payload["body"])
                                print(f"  Records: {body.get('total_records', 'N/A')}")
                                print(f"  Ponds queried: {body.get('ponds_queried', [])}")
                            except:
                                pass
                    else:
                        ai_data["tests"][f"test_{i+1}"] = {
                            "status": f"✗ Failed (HTTP {response['StatusCode']})"
                        }
                        print(f"  {RED}✗ Failed{RESET} - HTTP {response['StatusCode']}")

                except lambda_client.exceptions.ResourceNotFoundException:
                    ai_data["tests"][f"test_{i+1}"] = {"status": "✗ Function not found"}
                    print(f"  {RED}✗ Function not found{RESET}")
                    break
                except Exception as e:
                    ai_data["tests"][f"test_{i+1}"] = {"status": f"✗ Error: {str(e)}"}
                    print(f"  {RED}✗ Error: {str(e)}{RESET}")

        except lambda_client.exceptions.ResourceNotFoundException:
            ai_data["status"] = "✗ Function not found"
            print(f"{RED}AI Query Handler function not found{RESET}")
        except Exception as e:
            ai_data["status"] = f"✗ Error: {str(e)}"
            print(f"{RED}Error analyzing AI handler: {str(e)}{RESET}")

        self.report["ai_handler"] = ai_data
        return ai_data

    def generate_summary(self) -> Dict:
        """Generate summary report"""
        print(f"\n{CYAN}=== GENERATING SUMMARY ==={RESET}")

        summary = {
            "lambda_status": self._get_lambda_status(),
            "data_consumption": self._get_data_consumption_status(),
            "medallion_status": self._get_medallion_status(),
            "endpoint_coverage": self._get_endpoint_coverage(),
            "ai_status": self._get_ai_status(),
            "overall_health": "OPERATIONAL",
        }

        self.report["summary"] = summary
        return summary

    def _get_lambda_status(self) -> str:
        lambdas = self.report.get("lambdas", {}).get("functions", {})
        active = sum(1 for f in lambdas.values() if "Active" in f.get("status", ""))
        total = len(lambdas)
        if active == total:
            return f"✓ All {total} functions active"
        elif active > 0:
            return f"⚠ {active}/{total} functions active"
        else:
            return "✗ No functions active"

    def _get_data_consumption_status(self) -> str:
        s3 = self.report.get("s3", {})
        total_gb = s3.get("total_size_gb", 0)
        if total_gb > 100:
            return f"✓ Healthy consumption ({total_gb:.2f} GB)"
        elif total_gb > 10:
            return f"⚠ Moderate consumption ({total_gb:.2f} GB)"
        else:
            return f"✗ Low consumption ({total_gb:.2f} GB)"

    def _get_medallion_status(self) -> str:
        medallion = self.report.get("medallion", {})
        ratios = medallion.get("transformation_ratios", {})
        ponds_with_data = sum(1 for p in medallion.get("ponds", {}).values() if p.get("bronze_mb", 0) > 0)
        total_ponds = len(PONDS)
        if ponds_with_data == total_ponds:
            return f"✓ All {total_ponds} ponds transforming data"
        elif ponds_with_data > 0:
            return f"⚠ {ponds_with_data}/{total_ponds} ponds active"
        else:
            return "✗ No medallion data"

    def _get_endpoint_coverage(self) -> str:
        endpoints = self.report.get("endpoints", {})
        active = endpoints.get("active_endpoints", 0)
        inactive = endpoints.get("inactive_endpoints", 0)
        total = active + inactive
        if active == total and total > 0:
            return f"✓ Full coverage ({active}/{total} endpoints active)"
        elif active > 0:
            return f"⚠ Partial coverage ({active}/{total} endpoints active)"
        else:
            return "✗ No active endpoints"

    def _get_ai_status(self) -> str:
        ai = self.report.get("ai_handler", {})
        if "not found" in ai.get("status", "").lower():
            return "✗ AI handler not deployed"
        elif "Active" in ai.get("status", ""):
            tests = ai.get("tests", {})
            passed = sum(1 for t in tests.values() if "Success" in t.get("status", ""))
            total = len(tests)
            if passed == total and total > 0:
                return f"✓ AI handler working ({passed}/{total} tests passed)"
            elif passed > 0:
                return f"⚠ AI handler partially working ({passed}/{total} tests)"
            else:
                return "✗ AI handler tests failing"
        else:
            return f"✗ AI handler: {ai.get('status', 'Unknown')}"

    def print_report(self):
        """Print formatted report"""
        print(f"\n\n{BOLD}{CYAN}{'='*80}")
        print(f"NOAA FEDERATED DATA LAKE - COMPREHENSIVE DIAGNOSTIC REPORT")
        print(f"{'='*80}{RESET}\n")

        print(f"Environment: {self.report.get('environment')}")
        print(f"Generated: {self.report.get('timestamp')}\n")

        # Lambda Status
        print(f"{BOLD}{CYAN}LAMBDA FUNCTIONS{RESET}")
        print(f"-" * 80)
        lambdas = self.report.get("lambdas", {})
        print(f"Total Invocations (24h): {lambdas.get('total_invocations', 0)}")
        print(f"Total Errors (24h): {lambdas.get('total_errors', 0)}")
        for pond, func in lambdas.get("functions", {}).items():
            status_icon = "✓" if "Active" in func.get("status", "") else "✗"
            print(f"  {status_icon} {pond:15} - {func.get('status', 'N/A')}")

        # S3 Data
        print(f"\n{BOLD}{CYAN}S3 DATA CONSUMPTION{RESET}")
        print(f"-" * 80)
        s3 = self.report.get("s3", {})
        print(f"Bucket: {s3.get('bucket', 'N/A')}")
        print(f"Total Objects: {s3.get('total_objects', 0)}")
        print(f"Total Size: {s3.get('total_size_gb', 0):.2f} GB")
        print(f"\nBy Layer:")
        for layer, data in s3.get("layers", {}).items():
            print(f"  {layer.
