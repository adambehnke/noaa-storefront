#!/usr/bin/env python3
"""
Comprehensive Data Ingestion Scheduler for NOAA Federated Data Lake
Schedules and executes data ingestion from ALL NOAA endpoints every 15 minutes

This ensures that every question is answerable with fresh data across all ponds:
- Atmospheric Pond (NWS Weather, Alerts, Forecasts)
- Oceanic Pond (CO-OPS Tides, Water Levels, Currents)
- Buoy Pond (NDBC Buoy Observations)
- Climate Pond (NCEI Historical Data)
- Spatial Pond (Geographic Reference Data)
- Terrestrial Pond (Land-based Observations)

Usage:
    python schedule_all_ingestions.py --action create_schedules --env dev
    python schedule_all_ingestions.py --action trigger_all --env dev
    python schedule_all_ingestions.py --action status --env dev

Author: NOAA Federated Data Lake Team
Version: 1.0
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# AWS Clients
events_client = boto3.client("events", region_name="us-east-1")
lambda_client = boto3.client("lambda", region_name="us-east-1")
cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")

# =============================================================================
# CONFIGURATION - All Data Ponds and Their Ingestion Lambda Functions
# =============================================================================

INGESTION_LAMBDAS = {
    "atmospheric": {
        "function_name": "noaa-ingest-atmospheric-{env}",
        "description": "NWS weather, forecasts, and alerts",
        "schedule": "rate(15 minutes)",
        "timeout": 300,
        "endpoints_covered": [
            "NWS Weather Observations API",
            "NWS Forecast API",
            "NWS Alerts API",
            "NWS Warnings API",
            "Weather.gov Current Conditions",
        ],
        "priority": "critical",
        "payload": {"env": "{env}"},
    },
    "oceanic": {
        "function_name": "noaa-ingest-oceanic-{env}",
        "description": "CO-OPS tides, water levels, and currents",
        "schedule": "rate(15 minutes)",
        "timeout": 300,
        "endpoints_covered": [
            "CO-OPS Water Levels API",
            "CO-OPS Predictions API",
            "CO-OPS Currents API",
            "CO-OPS Meteorological Data API",
            "Tides and Currents API",
        ],
        "priority": "critical",
        "payload": {"env": "{env}", "hours_back": 1},
    },
    "buoy": {
        "function_name": "noaa-ingest-buoy-{env}",
        "description": "NDBC buoy observations",
        "schedule": "rate(15 minutes)",
        "timeout": 300,
        "endpoints_covered": [
            "NDBC Standard Meteorological Data",
            "NDBC Spectral Wave Data",
            "NDBC Continuous Winds",
            "NDBC Ocean Data",
        ],
        "priority": "high",
        "payload": {"env": "{env}"},
    },
    "climate": {
        "function_name": "noaa-ingest-climate-{env}",
        "description": "NCEI historical climate data",
        "schedule": "rate(60 minutes)",  # Less frequent, historical data
        "timeout": 600,
        "endpoints_covered": [
            "NCEI Climate Data Online (CDO) API",
            "NCEI Global Summary of the Day",
            "NCEI Local Climatological Data",
            "NCEI Normals API",
        ],
        "priority": "medium",
        "payload": {"env": "{env}"},
    },
    "spatial": {
        "function_name": "noaa-ingest-spatial-{env}",
        "description": "Geographic and spatial reference data",
        "schedule": "rate(6 hours)",  # Reference data, updates infrequently
        "timeout": 300,
        "endpoints_covered": [
            "Coastal Station Metadata",
            "Buoy Station Locations",
            "Geographic Boundaries",
        ],
        "priority": "low",
        "payload": {"env": "{env}"},
    },
    "terrestrial": {
        "function_name": "noaa-ingest-terrestrial-{env}",
        "description": "Land-based environmental observations",
        "schedule": "rate(30 minutes)",
        "timeout": 300,
        "endpoints_covered": [
            "USGS Stream Gauges",
            "Precipitation Data",
            "Soil Moisture",
        ],
        "priority": "medium",
        "payload": {"env": "{env}"},
    },
}


# =============================================================================
# SCHEDULER FUNCTIONS
# =============================================================================


def create_all_schedules(env: str) -> Dict:
    """
    Create EventBridge schedules for all data pond ingestion Lambdas
    """
    print(f"\n{'=' * 70}")
    print(f"Creating Ingestion Schedules for Environment: {env}")
    print(f"{'=' * 70}\n")

    results = {"success": [], "failed": [], "skipped": []}

    for pond_name, config in INGESTION_LAMBDAS.items():
        function_name = config["function_name"].format(env=env)
        rule_name = f"noaa-ingest-{pond_name}-schedule-{env}"
        schedule = config["schedule"]

        print(f"[{pond_name.upper()}] Creating schedule: {schedule}")
        print(f"  Function: {function_name}")
        print(f"  Priority: {config['priority']}")

        try:
            # Check if Lambda exists
            try:
                lambda_client.get_function(FunctionName=function_name)
                function_exists = True
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    function_exists = False
                    print(f"  ⚠️  Lambda function not found: {function_name}")
                    results["skipped"].append(
                        {
                            "pond": pond_name,
                            "reason": "Lambda function does not exist",
                            "function": function_name,
                        }
                    )
                    continue
                else:
                    raise

            # Create or update EventBridge rule
            rule_response = events_client.put_rule(
                Name=rule_name,
                ScheduleExpression=schedule,
                State="ENABLED",
                Description=f"Ingest {config['description']} every 15 minutes",
            )

            print(f"  ✓ Created/Updated EventBridge rule: {rule_name}")

            # Get Lambda ARN
            lambda_info = lambda_client.get_function(FunctionName=function_name)
            lambda_arn = lambda_info["Configuration"]["FunctionArn"]

            # Add Lambda as target
            target_payload = json.dumps(config["payload"]).replace("{env}", env)

            events_client.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        "Id": f"{pond_name}-ingestion-target",
                        "Arn": lambda_arn,
                        "Input": target_payload,
                    }
                ],
            )

            print(f"  ✓ Added Lambda target to rule")

            # Add Lambda permission for EventBridge to invoke
            try:
                lambda_client.add_permission(
                    FunctionName=function_name,
                    StatementId=f"AllowEventBridge-{rule_name}",
                    Action="lambda:InvokeFunction",
                    Principal="events.amazonaws.com",
                    SourceArn=rule_response["RuleArn"],
                )
                print(f"  ✓ Added EventBridge invoke permission")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceConflictException":
                    print(f"  ℹ️  Permission already exists (OK)")
                else:
                    raise

            results["success"].append(
                {
                    "pond": pond_name,
                    "function": function_name,
                    "rule": rule_name,
                    "schedule": schedule,
                }
            )

            print(f"  ✅ Schedule created successfully\n")

        except Exception as e:
            print(f"  ❌ Error creating schedule: {e}\n")
            results["failed"].append(
                {"pond": pond_name, "function": function_name, "error": str(e)}
            )

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"SCHEDULE CREATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"✅ Success: {len(results['success'])} ponds")
    print(f"❌ Failed:  {len(results['failed'])} ponds")
    print(f"⚠️  Skipped: {len(results['skipped'])} ponds")
    print(f"{'=' * 70}\n")

    if results["success"]:
        print("Successfully scheduled:")
        for item in results["success"]:
            print(f"  • {item['pond']}: {item['schedule']}")

    if results["failed"]:
        print("\nFailed:")
        for item in results["failed"]:
            print(f"  • {item['pond']}: {item['error']}")

    if results["skipped"]:
        print("\nSkipped (Lambda not deployed):")
        for item in results["skipped"]:
            print(f"  • {item['pond']}: {item['reason']}")

    return results


def trigger_all_ingestions(env: str) -> Dict:
    """
    Manually trigger all ingestion Lambdas immediately (for testing/backfill)
    """
    print(f"\n{'=' * 70}")
    print(f"Triggering All Ingestions for Environment: {env}")
    print(f"{'=' * 70}\n")

    results = {"success": [], "failed": []}

    for pond_name, config in INGESTION_LAMBDAS.items():
        function_name = config["function_name"].format(env=env)
        payload = json.dumps(config["payload"]).replace("{env}", env)

        print(f"[{pond_name.upper()}] Triggering ingestion...")
        print(f"  Function: {function_name}")

        try:
            # Invoke Lambda asynchronously
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",  # Async invocation
                Payload=payload,
            )

            if response["StatusCode"] == 202:
                print(f"  ✅ Triggered successfully (async)\n")
                results["success"].append(
                    {"pond": pond_name, "function": function_name}
                )
            else:
                print(f"  ⚠️  Unexpected status code: {response['StatusCode']}\n")
                results["failed"].append(
                    {
                        "pond": pond_name,
                        "function": function_name,
                        "error": f"Status code {response['StatusCode']}",
                    }
                )

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"  ⚠️  Lambda function not found (skipping)\n")
                results["failed"].append(
                    {
                        "pond": pond_name,
                        "function": function_name,
                        "error": "Function not found",
                    }
                )
            else:
                print(f"  ❌ Error: {e}\n")
                results["failed"].append(
                    {"pond": pond_name, "function": function_name, "error": str(e)}
                )

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"MANUAL TRIGGER SUMMARY")
    print(f"{'=' * 70}")
    print(f"✅ Triggered: {len(results['success'])} ponds")
    print(f"❌ Failed:    {len(results['failed'])} ponds")
    print(f"{'=' * 70}\n")

    return results


def check_ingestion_status(env: str) -> Dict:
    """
    Check the status of all ingestion schedules and recent executions
    """
    print(f"\n{'=' * 70}")
    print(f"Checking Ingestion Status for Environment: {env}")
    print(f"{'=' * 70}\n")

    status = {"schedules": [], "recent_executions": []}

    for pond_name, config in INGESTION_LAMBDAS.items():
        function_name = config["function_name"].format(env=env)
        rule_name = f"noaa-ingest-{pond_name}-schedule-{env}"

        print(f"[{pond_name.upper()}]")
        print(f"  Function: {function_name}")

        pond_status = {
            "pond": pond_name,
            "function": function_name,
            "schedule_enabled": False,
            "lambda_exists": False,
            "recent_errors": 0,
            "recent_invocations": 0,
        }

        # Check if Lambda exists
        try:
            lambda_info = lambda_client.get_function(FunctionName=function_name)
            pond_status["lambda_exists"] = True
            print(f"  ✓ Lambda exists")

            # Get recent invocations from CloudWatch
            try:
                end_time = datetime.utcnow()
                start_time = datetime.utcnow().replace(
                    hour=end_time.hour - 1,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

                # Get invocation metrics
                invocations = cloudwatch.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Invocations",
                    Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=["Sum"],
                )

                if invocations["Datapoints"]:
                    pond_status["recent_invocations"] = int(
                        invocations["Datapoints"][0]["Sum"]
                    )
                    print(
                        f"  ℹ️  Invocations (last hour): {pond_status['recent_invocations']}"
                    )

                # Get error metrics
                errors = cloudwatch.get_metric_statistics(
                    Namespace="AWS/Lambda",
                    MetricName="Errors",
                    Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=["Sum"],
                )

                if errors["Datapoints"]:
                    pond_status["recent_errors"] = int(errors["Datapoints"][0]["Sum"])
                    if pond_status["recent_errors"] > 0:
                        print(
                            f"  ⚠️  Errors (last hour): {pond_status['recent_errors']}"
                        )

            except Exception as e:
                print(f"  ⚠️  Could not fetch CloudWatch metrics: {e}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"  ❌ Lambda does not exist")
            else:
                print(f"  ❌ Error checking Lambda: {e}")

        # Check EventBridge schedule
        try:
            rule = events_client.describe_rule(Name=rule_name)
            pond_status["schedule_enabled"] = rule["State"] == "ENABLED"
            pond_status["schedule_expression"] = rule.get("ScheduleExpression", "N/A")

            if pond_status["schedule_enabled"]:
                print(f"  ✓ Schedule enabled: {rule['ScheduleExpression']}")
            else:
                print(f"  ⚠️  Schedule disabled")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"  ❌ Schedule does not exist")
            else:
                print(f"  ⚠️  Error checking schedule: {e}")

        status["schedules"].append(pond_status)
        print()

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"STATUS SUMMARY")
    print(f"{'=' * 70}")

    total_ponds = len(INGESTION_LAMBDAS)
    lambdas_deployed = sum(1 for s in status["schedules"] if s["lambda_exists"])
    schedules_enabled = sum(1 for s in status["schedules"] if s["schedule_enabled"])
    total_invocations = sum(s["recent_invocations"] for s in status["schedules"])
    total_errors = sum(s["recent_errors"] for s in status["schedules"])

    print(f"Total Data Ponds:       {total_ponds}")
    print(f"Lambdas Deployed:       {lambdas_deployed}/{total_ponds}")
    print(f"Schedules Enabled:      {schedules_enabled}/{total_ponds}")
    print(f"Recent Invocations:     {total_invocations} (last hour)")
    print(f"Recent Errors:          {total_errors} (last hour)")
    print(f"{'=' * 70}\n")

    if schedules_enabled == total_ponds and lambdas_deployed == total_ponds:
        print("✅ All ingestion pipelines are operational!\n")
    else:
        print("⚠️  Some ingestion pipelines need attention:\n")
        for s in status["schedules"]:
            if not s["lambda_exists"]:
                print(f"  • {s['pond']}: Lambda not deployed")
            elif not s["schedule_enabled"]:
                print(f"  • {s['pond']}: Schedule not enabled")

    return status


def delete_all_schedules(env: str) -> Dict:
    """
    Delete all EventBridge schedules (cleanup)
    """
    print(f"\n{'=' * 70}")
    print(f"Deleting All Ingestion Schedules for Environment: {env}")
    print(f"{'=' * 70}\n")

    results = {"deleted": [], "not_found": [], "failed": []}

    for pond_name, config in INGESTION_LAMBDAS.items():
        rule_name = f"noaa-ingest-{pond_name}-schedule-{env}"

        print(f"[{pond_name.upper()}] Deleting schedule: {rule_name}")

        try:
            # Remove all targets first
            try:
                targets = events_client.list_targets_by_rule(Rule=rule_name)
                if targets["Targets"]:
                    target_ids = [t["Id"] for t in targets["Targets"]]
                    events_client.remove_targets(Rule=rule_name, Ids=target_ids)
                    print(f"  ✓ Removed targets")
            except ClientError:
                pass

            # Delete the rule
            events_client.delete_rule(Name=rule_name)
            print(f"  ✅ Deleted successfully\n")

            results["deleted"].append({"pond": pond_name, "rule": rule_name})

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"  ℹ️  Rule not found (already deleted)\n")
                results["not_found"].append({"pond": pond_name, "rule": rule_name})
            else:
                print(f"  ❌ Error: {e}\n")
                results["failed"].append(
                    {"pond": pond_name, "rule": rule_name, "error": str(e)}
                )

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"DELETION SUMMARY")
    print(f"{'=' * 70}")
    print(f"✅ Deleted:   {len(results['deleted'])} schedules")
    print(f"ℹ️  Not Found: {len(results['not_found'])} schedules")
    print(f"❌ Failed:    {len(results['failed'])} schedules")
    print(f"{'=' * 70}\n")

    return results


def list_all_endpoints(env: str):
    """
    List all NOAA API endpoints being ingested
    """
    print(f"\n{'=' * 70}")
    print(f"NOAA API Endpoints Being Ingested (Environment: {env})")
    print(f"{'=' * 70}\n")

    total_endpoints = 0

    for pond_name, config in INGESTION_LAMBDAS.items():
        print(f"[{pond_name.upper()} POND]")
        print(f"  Description: {config['description']}")
        print(f"  Schedule: {config['schedule']}")
        print(f"  Priority: {config['priority']}")
        print(f"  Endpoints:")

        for endpoint in config["endpoints_covered"]:
            print(f"    • {endpoint}")
            total_endpoints += 1

        print()

    print(f"{'=' * 70}")
    print(f"Total Endpoints: {total_endpoints}")
    print(f"Total Ponds: {len(INGESTION_LAMBDAS)}")
    print(f"{'=' * 70}\n")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="NOAA Federated Data Lake - Comprehensive Ingestion Scheduler"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=[
            "create_schedules",
            "trigger_all",
            "status",
            "delete_schedules",
            "list_endpoints",
        ],
        help="Action to perform",
    )
    parser.add_argument(
        "--env", default="dev", help="Environment (dev/prod) - default: dev"
    )

    args = parser.parse_args()

    print(f"\n🌊 NOAA Federated Data Lake - Ingestion Scheduler")
    print(f"   Environment: {args.env}")
    print(f"   Action: {args.action}")
    print(f"   Time: {datetime.utcnow().isoformat()}")

    try:
        if args.action == "create_schedules":
            result = create_all_schedules(args.env)
            if result["failed"]:
                sys.exit(1)

        elif args.action == "trigger_all":
            result = trigger_all_ingestions(args.env)
            print(
                "\n⏳ All Lambdas triggered asynchronously. Check CloudWatch Logs for results."
            )
            if result["failed"]:
                sys.exit(1)

        elif args.action == "status":
            result = check_ingestion_status(args.env)

        elif args.action == "delete_schedules":
            confirm = input(
                f"\n⚠️  Are you sure you want to delete ALL schedules for {args.env}? (yes/no): "
            )
            if confirm.lower() == "yes":
                result = delete_all_schedules(args.env)
            else:
                print("❌ Deletion cancelled.")
                sys.exit(0)

        elif args.action == "list_endpoints":
            list_all_endpoints(args.env)

        print("\n✅ Operation completed successfully!\n")

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
