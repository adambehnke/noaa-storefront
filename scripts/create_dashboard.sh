#!/bin/bash

aws cloudwatch put-dashboard \
  --dashboard-name "NOAA-DataLake-Health-dev" \
  --dashboard-body '{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# NOAA Federated Data Lake - System Health Dashboard\n**Account:** 899626030376 | **Environment:** dev | **Last Updated:** Realtime"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Invocations", { "stat": "Sum" } ],
          [ ".", "Errors", { "stat": "Sum", "yAxis": "right" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Invocations & Errors",
        "period": 300,
        "yAxis": {
          "left": {"label": "Invocations"},
          "right": {"label": "Errors"}
        }
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Duration", { "stat": "Average" } ],
          [ "...", { "stat": "Maximum" } ]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "us-east-1",
        "title": "Lambda Execution Duration",
        "period": 300,
        "yAxis": {
          "left": {"label": "Milliseconds"}
        }
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 6,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Invocations", { "stat": "Sum" } ]
        ],
        "view": "singleValue",
        "region": "us-east-1",
        "title": "Total Invocations (1hr)",
        "period": 3600
      }
    },
    {
      "type": "metric",
      "x": 6,
      "y": 8,
      "width": 6,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Errors", { "stat": "Sum" } ]
        ],
        "view": "singleValue",
        "region": "us-east-1",
        "title": "Total Errors (1hr)",
        "period": 3600
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 8,
      "width": 6,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "ConcurrentExecutions", { "stat": "Maximum" } ]
        ],
        "view": "singleValue",
        "region": "us-east-1",
        "title": "Peak Concurrency (1hr)",
        "period": 3600
      }
    },
    {
      "type": "metric",
      "x": 18,
      "y": 8,
      "width": 6,
      "height": 6,
      "properties": {
        "metrics": [
          [ "AWS/Lambda", "Throttles", { "stat": "Sum" } ]
        ],
        "view": "singleValue",
        "region": "us-east-1",
        "title": "Throttles (1hr)",
        "period": 3600
      }
    }
  ]
}'

echo "Dashboard created successfully!"
echo "View at: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-DataLake-Health-dev"
