#!/usr/bin/env python3
"""
NOAA Federated Data Lake - CloudWatch Dashboard Deployment
Creates 3 comprehensive monitoring dashboards
"""

import json
import os
import sys

import boto3

# Configuration
AWS_PROFILE = os.environ.get("AWS_PROFILE", "noaa-target")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


def create_session():
    """Create AWS session with profile"""
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        return session.client("cloudwatch")
    except Exception as e:
        print(f"❌ Error creating AWS session: {e}")
        print(f"Make sure profile '{AWS_PROFILE}' exists in ~/.aws/credentials")
        sys.exit(1)


def create_ingestion_dashboard(client, dashboard_name):
    """Create Data Ingestion Flow Dashboard"""
    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# 📥 NOAA Data Ingestion Flow\nMonitor Lambda functions ingesting data from NOAA APIs"
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 2,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Lambda Invocations (Last 24h)",
                    "metrics": [["AWS/Lambda", "Invocations", {"stat": "Sum"}]],
                    "period": 300,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 12,
                "y": 2,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Lambda Errors",
                    "metrics": [["AWS/Lambda", "Errors", {"stat": "Sum"}]],
                    "period": 300,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 8,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Average Duration",
                    "metrics": [["AWS/Lambda", "Duration", {"stat": "Average"}]],
                    "period": 300,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                    "yAxis": {"left": {"label": "Milliseconds"}},
                },
            },
            {
                "type": "metric",
                "x": 8,
                "y": 8,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Concurrent Executions",
                    "metrics": [
                        ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum"}]
                    ],
                    "period": 60,
                    "stat": "Maximum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 16,
                "y": 8,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Success Rate",
                    "metrics": [
                        [
                            "AWS/Lambda",
                            "Invocations",
                            {"stat": "Sum", "id": "m1", "visible": False},
                        ],
                        [".", "Errors", {"stat": "Sum", "id": "m2", "visible": False}],
                        [
                            {
                                "expression": "100*(m1-m2)/m1",
                                "label": "Success %",
                                "id": "e1",
                            }
                        ],
                    ],
                    "period": 300,
                    "region": AWS_REGION,
                    "view": "timeSeries",
                    "yAxis": {"left": {"min": 0, "max": 100}},
                },
            },
        ]
    }

    try:
        client.put_dashboard(
            DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body)
        )
        return True
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return False


def create_health_dashboard(client, dashboard_name):
    """Create System Health Dashboard"""
    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# 💚 NOAA System Health\nOverall system status and performance metrics"
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 2,
                "width": 6,
                "height": 6,
                "properties": {
                    "title": "Total Invocations (24h)",
                    "metrics": [["AWS/Lambda", "Invocations", {"stat": "Sum"}]],
                    "period": 86400,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "singleValue",
                },
            },
            {
                "type": "metric",
                "x": 6,
                "y": 2,
                "width": 6,
                "height": 6,
                "properties": {
                    "title": "Total Errors (24h)",
                    "metrics": [["AWS/Lambda", "Errors", {"stat": "Sum"}]],
                    "period": 86400,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "singleValue",
                },
            },
            {
                "type": "metric",
                "x": 12,
                "y": 2,
                "width": 6,
                "height": 6,
                "properties": {
                    "title": "Avg Duration (ms)",
                    "metrics": [["AWS/Lambda", "Duration", {"stat": "Average"}]],
                    "period": 3600,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "view": "singleValue",
                },
            },
            {
                "type": "metric",
                "x": 18,
                "y": 2,
                "width": 6,
                "height": 6,
                "properties": {
                    "title": "Step Functions",
                    "metrics": [["AWS/States", "ExecutionsSucceeded", {"stat": "Sum"}]],
                    "period": 86400,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "singleValue",
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 8,
                "width": 24,
                "height": 6,
                "properties": {
                    "title": "Error Rate Over Time",
                    "metrics": [
                        [
                            "AWS/Lambda",
                            "Errors",
                            {"stat": "Sum", "id": "errors", "visible": False},
                        ],
                        [
                            ".",
                            "Invocations",
                            {"stat": "Sum", "id": "invocations", "visible": False},
                        ],
                        [
                            {
                                "expression": "100*errors/invocations",
                                "label": "Error Rate %",
                            }
                        ],
                    ],
                    "period": 300,
                    "region": AWS_REGION,
                    "view": "timeSeries",
                    "yAxis": {"left": {"min": 0, "max": 10}},
                },
            },
        ]
    }

    try:
        client.put_dashboard(
            DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body)
        )
        return True
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return False


def create_data_quality_dashboard(client, dashboard_name):
    """Create Data Quality & Storage Dashboard"""
    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# 📊 NOAA Data Quality & Storage\nMonitor storage, Athena queries, and Glue jobs"
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "S3 Storage",
                    "metrics": [["AWS/S3", "BucketSizeBytes", {"stat": "Average"}]],
                    "period": 86400,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 8,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "S3 Objects",
                    "metrics": [["AWS/S3", "NumberOfObjects", {"stat": "Average"}]],
                    "period": 86400,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 16,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Athena Data Scanned",
                    "metrics": [["AWS/Athena", "DataScannedInBytes", {"stat": "Sum"}]],
                    "period": 3600,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 8,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Glue Job Activity",
                    "metrics": [
                        [
                            "AWS/Glue",
                            "glue.driver.aggregate.numCompletedTasks",
                            {"stat": "Sum"},
                        ]
                    ],
                    "period": 3600,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 12,
                "y": 8,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Lambda Throttles",
                    "metrics": [["AWS/Lambda", "Throttles", {"stat": "Sum"}]],
                    "period": 300,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
        ]
    }

    try:
        client.put_dashboard(
            DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body)
        )
        return True
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return False


def create_ai_query_dashboard(client, dashboard_name):
    """Create AI Query Processing Dashboard"""
    dashboard_body = {
        "widgets": [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "# 🤖 NOAA AI Query Processing\nMonitor AI-powered natural language queries and Athena execution"
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "AI Query Volume",
                    "metrics": [["AWS/Lambda", "Invocations", {"stat": "Sum"}]],
                    "period": 300,
                    "stat": "Sum",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 8,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Query Response Time",
                    "metrics": [
                        [
                            "AWS/Lambda",
                            "Duration",
                            {"stat": "Average", "label": "Avg Duration"},
                        ],
                        ["...", {"stat": "p99", "label": "P99 Duration"}],
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                    "yAxis": {"left": {"label": "Milliseconds"}},
                },
            },
            {
                "type": "metric",
                "x": 16,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Query Success Rate",
                    "metrics": [
                        [
                            "AWS/Lambda",
                            "Invocations",
                            {"stat": "Sum", "id": "m1", "visible": False},
                        ],
                        [".", "Errors", {"stat": "Sum", "id": "m2", "visible": False}],
                        [
                            {
                                "expression": "100*(m1-m2)/m1",
                                "label": "Success %",
                                "id": "e1",
                            }
                        ],
                    ],
                    "period": 300,
                    "region": AWS_REGION,
                    "view": "timeSeries",
                    "yAxis": {"left": {"min": 0, "max": 100}},
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 8,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Athena Query Performance",
                    "metrics": [
                        [
                            "AWS/Athena",
                            "DataScannedInBytes",
                            {"stat": "Sum", "label": "Data Scanned"},
                        ],
                        [
                            ".",
                            "EngineExecutionTime",
                            {
                                "stat": "Average",
                                "label": "Execution Time",
                                "yAxis": "right",
                            },
                        ],
                    ],
                    "period": 300,
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
            {
                "type": "metric",
                "x": 12,
                "y": 8,
                "width": 12,
                "height": 6,
                "properties": {
                    "title": "Athena Queries Executed",
                    "metrics": [
                        [
                            "AWS/Athena",
                            "TotalExecutionTime",
                            {"stat": "SampleCount", "label": "Query Count"},
                        ]
                    ],
                    "period": 3600,
                    "stat": "SampleCount",
                    "region": AWS_REGION,
                    "view": "timeSeries",
                },
            },
        ]
    }

    try:
        client.put_dashboard(
            DashboardName=dashboard_name, DashboardBody=json.dumps(dashboard_body)
        )
        return True
    except Exception as e:
        print(f"❌ Error creating dashboard: {e}")
        return False


def main():
    print("=" * 60)
    print("NOAA CloudWatch Dashboard Deployment")
    print("=" * 60)
    print(f"Profile: {AWS_PROFILE}")
    print(f"Region:  {AWS_REGION}")
    print(f"Env:     {ENVIRONMENT}")
    print()

    # Create CloudWatch client
    client = create_session()

    # Dashboard names
    dashboards = [
        (
            f"NOAA-Data-Ingestion-Flow-{ENVIRONMENT}",
            create_ingestion_dashboard,
            "Data Ingestion Flow",
        ),
        (f"NOAA-System-Health-{ENVIRONMENT}", create_health_dashboard, "System Health"),
        (
            f"NOAA-Data-Quality-{ENVIRONMENT}",
            create_data_quality_dashboard,
            "Data Quality & Storage",
        ),
        (
            f"NOAA-AI-Query-Processing-{ENVIRONMENT}",
            create_ai_query_dashboard,
            "AI Query Processing",
        ),
    ]

    # Create each dashboard
    success_count = 0
    for dashboard_name, create_func, display_name in dashboards:
        print(f"📊 Creating {display_name} Dashboard...")
        if create_func(client, dashboard_name):
            print(f"✅ {display_name} Dashboard created successfully!")
            print(
                f"   URL: https://console.aws.amazon.com/cloudwatch/home?region={AWS_REGION}#dashboards:name={dashboard_name}"
            )
            success_count += 1
        else:
            print(f"❌ Failed to create {display_name} Dashboard")
        print()

    # Verify dashboards exist
    print("🔍 Verifying dashboards...")
    try:
        response = client.list_dashboards()
        noaa_dashboards = [
            d["DashboardName"]
            for d in response["DashboardEntries"]
            if "NOAA" in d["DashboardName"]
        ]

        if noaa_dashboards:
            print(f"✅ Found {len(noaa_dashboards)} NOAA dashboard(s):")
            for name in noaa_dashboards:
                print(f"   - {name}")
        else:
            print("⚠️  No NOAA dashboards found")
    except Exception as e:
        print(f"❌ Error verifying dashboards: {e}")

    print()
    print("=" * 60)
    if success_count == len(dashboards):
        print("✨ All dashboards deployed successfully!")
    else:
        print(f"⚠️  {success_count}/{len(dashboards)} dashboards deployed")
    print("=" * 60)
    print()
    print("📖 Access your dashboards:")
    print(
        f"   https://console.aws.amazon.com/cloudwatch/home?region={AWS_REGION}#dashboards:"
    )
    print()


if __name__ == "__main__":
    main()
