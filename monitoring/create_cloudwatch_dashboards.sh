#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - CloudWatch Dashboard Deployment
#
# This script creates comprehensive CloudWatch dashboards to visualize:
# - Data ingestion flow
# - Medallion architecture conversion (Bronze → Silver → Gold)
# - AI query processing
# - System health and performance
#
# Usage:
#   ./create_cloudwatch_dashboards.sh
#
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Source environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config/environment.sh"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   NOAA CloudWatch Dashboard Deployment                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Dashboard 1: Data Ingestion Flow
###############################################################################

create_ingestion_dashboard() {
    echo -e "${GREEN}Creating Ingestion Flow Dashboard...${NC}"

    aws cloudwatch put-dashboard \
        --dashboard-name "NOAA-Data-Ingestion-Flow-${ENVIRONMENT}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --dashboard-body '{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# 📥 NOAA Data Ingestion Flow\n## Real-time monitoring of data flowing into the system from NOAA APIs"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Lambda Invocations by Pond (Last 24h)",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Atmospheric"}, {"dimensions": {"FunctionName": "'${LAMBDA_ATMOSPHERIC}'"}}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_OCEANIC}'"}, "label": "Oceanic"}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_BUOY}'"}, "label": "Buoy"}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_CLIMATE}'"}, "label": "Climate"}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_TERRESTRIAL}'"}, "label": "Terrestrial"}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_SPATIAL}'"}, "label": "Spatial"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "yAxis": {"left": {"label": "Invocations"}},
        "view": "timeSeries",
        "stacked": false
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Ingestion Success Rate",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "id": "m1", "visible": false}],
          [".", "Errors", {"stat": "Sum", "id": "m2", "visible": false}],
          [{"expression": "100*(m1-m2)/m1", "label": "Success Rate %", "id": "e1"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "yAxis": {"left": {"min": 0, "max": 100}},
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Records Written to Bronze Layer",
        "metrics": [
          ["NOAA/DataLake", "RecordsIngested", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 8,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Average Ingestion Duration",
        "metrics": [
          ["AWS/Lambda", "Duration", {"stat": "Average", "dimensions": {"FunctionName": "'${LAMBDA_ATMOSPHERIC}'"}}, "label": "Atmospheric"],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_OCEANIC}'"}, "label": "Oceanic"}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_BUOY}'"}, "label": "Buoy"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "yAxis": {"left": {"label": "Milliseconds"}},
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 8,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Ingestion Errors",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum", "dimensions": {"FunctionName": "'${LAMBDA_ATMOSPHERIC}'"}}, "label": "Atmospheric"],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_OCEANIC}'"}, "label": "Oceanic"}],
          ["...", {"dimensions": {"FunctionName": "'${LAMBDA_BUOY}'"}, "label": "Buoy"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 14,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "Recent Ingestion Events",
        "query": "SOURCE '\''/aws/lambda/'${LAMBDA_ATMOSPHERIC}'\'' | SOURCE '\''/aws/lambda/'${LAMBDA_OCEANIC}'\'' | SOURCE '\''/aws/lambda/'${LAMBDA_BUOY}'\'' | fields @timestamp, @message | filter @message like /Ingested|records|Complete/ | sort @timestamp desc | limit 20",
        "region": "'${AWS_REGION}'"
      }
    }
  ]
}'

    echo -e "${GREEN}✓ Ingestion Flow Dashboard created${NC}"
}

###############################################################################
# Dashboard 2: Medallion Architecture Flow
###############################################################################

create_medallion_dashboard() {
    echo -e "${GREEN}Creating Medallion Architecture Dashboard...${NC}"

    aws cloudwatch put-dashboard \
        --dashboard-name "NOAA-Medallion-Architecture-${ENVIRONMENT}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --dashboard-body '{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# 🏛️ Medallion Architecture Flow: Bronze → Silver → Gold\n## Track data transformation through quality layers"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Bronze Layer - Raw Ingestion",
        "metrics": [
          ["NOAA/DataLake", "BronzeRecords", {"stat": "Sum", "label": "Records Written"}],
          [".", "BronzeBytes", {"stat": "Sum", "label": "Bytes Written", "yAxis": "right"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {
          "left": {"label": "Records"},
          "right": {"label": "Bytes"}
        }
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Silver Layer - Processed Data",
        "metrics": [
          ["NOAA/DataLake", "SilverRecords", {"stat": "Sum", "label": "Records Processed"}],
          [".", "SilverQualityScore", {"stat": "Average", "label": "Quality Score", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {
          "left": {"label": "Records"},
          "right": {"label": "Quality %", "min": 0, "max": 100}
        }
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Gold Layer - Analytics Ready",
        "metrics": [
          ["NOAA/DataLake", "GoldRecords", {"stat": "Sum", "label": "Records Available"}],
          [".", "GoldPartitions", {"stat": "Sum", "label": "Partitions Created", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {
          "left": {"label": "Records"},
          "right": {"label": "Partitions"}
        }
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Glue Job Executions (ETL Pipeline)",
        "metrics": [
          ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", {"stat": "Sum", "label": "Completed Tasks"}],
          [".", "glue.driver.aggregate.numFailedTasks", {"stat": "Sum", "label": "Failed Tasks"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Conversion Rate: Bronze → Gold",
        "metrics": [
          ["NOAA/DataLake", "BronzeRecords", {"stat": "Sum", "id": "bronze", "visible": false}],
          [".", "GoldRecords", {"stat": "Sum", "id": "gold", "visible": false}],
          [{"expression": "100*gold/bronze", "label": "Conversion Rate %", "id": "conversion"}]
        ],
        "period": 3600,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 14,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "Step Functions Pipeline Execution",
        "metrics": [
          ["AWS/States", "ExecutionSucceeded", {"stat": "Sum", "label": "Successful"}],
          [".", "ExecutionFailed", {"stat": "Sum", "label": "Failed"}],
          [".", "ExecutionTime", {"stat": "Average", "label": "Avg Duration (ms)", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 20,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "ETL Processing Logs",
        "query": "SOURCE '\''/aws/glue/jobs/output'\'' | fields @timestamp, @message | filter @message like /Bronze|Silver|Gold|Conversion/ | sort @timestamp desc | limit 20",
        "region": "'${AWS_REGION}'"
      }
    }
  ]
}'

    echo -e "${GREEN}✓ Medallion Architecture Dashboard created${NC}"
}

###############################################################################
# Dashboard 3: AI Query Processing
###############################################################################

create_ai_dashboard() {
    echo -e "${GREEN}Creating AI Query Processing Dashboard...${NC}"

    aws cloudwatch put-dashboard \
        --dashboard-name "NOAA-AI-Query-Processing-${ENVIRONMENT}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --dashboard-body '{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# 🤖 AI-Powered Query Processing\n## How Bedrock AI interprets and answers user queries across federated ponds"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "AI Query Volume",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "dimensions": {"FunctionName": "'${LAMBDA_AI_QUERY}'"}, "label": "Total Queries"}],
          [".", "Errors", {"stat": "Sum", "dimensions": {"FunctionName": "'${LAMBDA_AI_QUERY}'"}, "label": "Failed Queries"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
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
          ["AWS/Lambda", "Duration", {"stat": "Average", "dimensions": {"FunctionName": "'${LAMBDA_AI_QUERY}'"}, "label": "Avg Duration"}],
          ["...", {"stat": "p99", "label": "P99 Duration"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"label": "Milliseconds"}}
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Bedrock API Calls",
        "metrics": [
          ["AWS/Bedrock", "Invocations", {"stat": "Sum", "label": "AI Model Calls"}],
          [".", "InvocationLatency", {"stat": "Average", "label": "Avg Latency", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Ponds Queried per Request",
        "metrics": [
          ["NOAA/AI", "PondsQueried", {"stat": "Average", "label": "Avg Ponds per Query"}],
          [".", "ParallelQueries", {"stat": "Sum", "label": "Parallel Executions"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Query Interpretation Success",
        "metrics": [
          ["NOAA/AI", "QueryInterpretationSuccess", {"stat": "Sum", "label": "Successful"}],
          [".", "QueryInterpretationFailure", {"stat": "Sum", "label": "Failed"}],
          [".", "AmbiguousQueries", {"stat": "Sum", "label": "Ambiguous"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Athena Query Executions",
        "metrics": [
          ["AWS/Athena", "DataScannedInBytes", {"stat": "Sum", "label": "Data Scanned"}],
          [".", "QueryPlanningTime", {"stat": "Average", "label": "Planning Time", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Result Set Sizes",
        "metrics": [
          ["NOAA/AI", "ResultRows", {"stat": "Average", "label": "Avg Rows Returned"}],
          [".", "ResultBytes", {"stat": "Average", "label": "Avg Bytes Returned", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Cache Hit Rate",
        "metrics": [
          ["NOAA/AI", "CacheHits", {"stat": "Sum", "id": "hits", "visible": false}],
          [".", "CacheMisses", {"stat": "Sum", "id": "misses", "visible": false}],
          [{"expression": "100*hits/(hits+misses)", "label": "Cache Hit Rate %"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "log",
      "x": 0,
      "y": 20,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "User Query Interpretation",
        "query": "SOURCE '\''/aws/lambda/'${LAMBDA_AI_QUERY}'\'' | fields @timestamp, @message | filter @message like /User query|Interpreted|relevant ponds/ | sort @timestamp desc | limit 20",
        "region": "'${AWS_REGION}'"
      }
    },
    {
      "type": "log",
      "x": 12,
      "y": 20,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Query Results Summary",
        "query": "SOURCE '\''/aws/lambda/'${LAMBDA_AI_QUERY}'\'' | fields @timestamp, @message | filter @message like /Returning|results|rows/ | sort @timestamp desc | limit 20",
        "region": "'${AWS_REGION}'"
      }
    }
  ]
}'

    echo -e "${GREEN}✓ AI Query Processing Dashboard created${NC}"
}

###############################################################################
# Dashboard 4: System Health Overview
###############################################################################

create_system_health_dashboard() {
    echo -e "${GREEN}Creating System Health Dashboard...${NC}"

    aws cloudwatch put-dashboard \
        --dashboard-name "NOAA-System-Health-Overview-${ENVIRONMENT}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --dashboard-body '{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# 💚 System Health Overview\n## End-to-end monitoring of the NOAA Federated Data Lake"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Overall System Health",
        "metrics": [
          ["NOAA/Health", "SystemHealthScore", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "view": "singleValue",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric",
      "x": 6,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Total Records (24h)",
        "metrics": [
          ["NOAA/DataLake", "TotalRecords", {"stat": "Sum"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Active Lambdas",
        "metrics": [
          ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum"}]
        ],
        "period": 300,
        "stat": "Maximum",
        "region": "'${AWS_REGION}'",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 18,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Query Success Rate",
        "metrics": [
          ["NOAA/AI", "QuerySuccessRate", {"stat": "Average"}]
        ],
        "period": 3600,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "view": "singleValue",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "S3 Storage by Layer",
        "metrics": [
          ["AWS/S3", "BucketSizeBytes", {"stat": "Average", "dimensions": {"BucketName": "'${DATA_LAKE_BUCKET}'", "StorageType": "StandardStorage"}}]
        ],
        "period": 86400,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"label": "Bytes"}}
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Lambda Error Rate",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum", "id": "errors", "visible": false}],
          [".", "Invocations", {"stat": "Sum", "id": "invocations", "visible": false}],
          [{"expression": "100*errors/invocations", "label": "Error Rate %"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"min": 0, "max": 10}}
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Data Quality Score",
        "metrics": [
          ["NOAA/Quality", "CompletenessScore", {"stat": "Average", "label": "Completeness"}],
          [".", "TimelinessScore", {"stat": "Average", "label": "Timeliness"}],
          [".", "AccuracyScore", {"stat": "Average", "label": "Accuracy"}]
        ],
        "period": 3600,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"min": 0, "max": 100}}
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Cost Metrics (Estimated)",
        "metrics": [
          ["NOAA/Cost", "EstimatedDailyCost", {"stat": "Sum", "label": "Daily Cost"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"label": "USD"}}
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 14,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Alarm Status",
        "metrics": [
          ["AWS/CloudWatch", "AlarmStateChange", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    }
  ]
}'

    echo -e "${GREEN}✓ System Health Dashboard created${NC}"
}

###############################################################################
# Dashboard 5: Data Flow Visualization
###############################################################################

create_data_flow_dashboard() {
    echo -e "${GREEN}Creating Data Flow Visualization Dashboard...${NC}"

    aws cloudwatch put-dashboard \
        --dashboard-name "NOAA-Data-Flow-Visualization-${ENVIRONMENT}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --dashboard-body '{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 3,
      "properties": {
        "markdown": "# 🌊 Complete Data Flow Visualization\n\n```\nNOAA APIs → Lambda Ingest → S3 Bronze → Glue ETL → S3 Silver → Step Functions → S3 Gold → Athena → AI Query → Results\n```"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 3,
      "width": 4,
      "height": 4,
      "properties": {
        "title": "1️⃣ API Calls",
        "metrics": [
          ["NOAA/Ingestion", "APIRequests", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 4,
      "y": 3,
      "width": 4,
      "height": 4,
      "properties": {
        "title": "2️⃣ Lambda Ingest",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 8,
      "y": 3,
      "width": 4,
      "height": 4,
      "properties": {
        "title": "3️⃣ Bronze Records",
        "metrics": [
          ["NOAA/DataLake", "BronzeRecords", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 3,
      "width": 4,
      "height": 4,
      "properties": {
        "title": "4️⃣ ETL Jobs",
        "metrics": [
          ["AWS/Glue", "glue.ALL.jvm.heap.usage", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "'${AWS_REGION}'",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 3,
      "width": 4,
      "height": 4,
      "properties": {
        "title": "5️⃣ Gold Records",
        "
