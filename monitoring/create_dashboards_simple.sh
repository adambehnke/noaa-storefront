#!/bin/bash
###############################################################################
# Simplified CloudWatch Dashboard Deployment for NOAA
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config/environment.sh"

echo -e "${BLUE}Creating CloudWatch Dashboards...${NC}"
echo "Account: ${AWS_ACCOUNT_ID}"
echo "Region: ${AWS_REGION}"
echo ""

###############################################################################
# Dashboard 1: Data Ingestion Flow
###############################################################################

echo -e "${BLUE}[1/3] Creating Data Ingestion Flow Dashboard...${NC}"

aws cloudwatch put-dashboard \
  --dashboard-name "NOAA-Data-Ingestion-Flow-${ENVIRONMENT}" \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}" \
  --dashboard-body file://<(cat <<'DASHBOARD1'
{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# NOAA Data Ingestion Flow\nMonitor data flowing from NOAA APIs through Lambda to S3"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Lambda Invocations (Last 24h)",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 2,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Lambda Errors",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
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
        "title": "Average Lambda Duration",
        "metrics": [
          ["AWS/Lambda", "Duration", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "view": "timeSeries",
        "yAxis": {
          "left": {
            "label": "Milliseconds"
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 12,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Concurrent Lambda Executions",
        "metrics": [
          ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum"}]
        ],
        "period": 60,
        "stat": "Maximum",
        "region": "us-east-1",
        "view": "timeSeries"
      }
    }
  ]
}
DASHBOARD1
)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Data Ingestion Flow Dashboard created${NC}"
    echo "  URL: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-Data-Ingestion-Flow-${ENVIRONMENT}"
else
    echo -e "${RED}✗ Failed to create dashboard${NC}"
fi

echo ""

###############################################################################
# Dashboard 2: System Health
###############################################################################

echo -e "${BLUE}[2/3] Creating System Health Dashboard...${NC}"

aws cloudwatch put-dashboard \
  --dashboard-name "NOAA-System-Health-${ENVIRONMENT}" \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}" \
  --dashboard-body file://<(cat <<'DASHBOARD2'
{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# NOAA System Health Overview\nEnd-to-end monitoring of the federated data lake"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Total Invocations (24h)",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "us-east-1",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 6,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Total Errors (24h)",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "us-east-1",
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
        "title": "Success Rate",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "id": "m1", "visible": false}],
          [".", "Errors", {"stat": "Sum", "id": "m2", "visible": false}],
          [{"expression": "100*(m1-m2)/m1", "label": "Success %", "id": "e1"}]
        ],
        "period": 3600,
        "region": "us-east-1",
        "view": "timeSeries",
        "yAxis": {
          "left": {
            "min": 0,
            "max": 100
          }
        }
      }
    },
    {
      "type": "metric",
      "x": 18,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Step Functions",
        "metrics": [
          ["AWS/States", "ExecutionsSucceeded", {"stat": "Sum"}]
        ],
        "period": 3600,
        "stat": "Sum",
        "region": "us-east-1",
        "view": "singleValue"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 24,
      "height": 6,
      "properties": {
        "title": "Error Rate Trend",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum", "id": "errors", "visible": false}],
          [".", "Invocations", {"stat": "Sum", "id": "invocations", "visible": false}],
          [{"expression": "100*errors/invocations", "label": "Error Rate %", "id": "errorRate"}]
        ],
        "period": 300,
        "region": "us-east-1",
        "view": "timeSeries",
        "yAxis": {
          "left": {
            "min": 0,
            "max": 10
          }
        }
      }
    }
  ]
}
DASHBOARD2
)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ System Health Dashboard created${NC}"
    echo "  URL: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-System-Health-${ENVIRONMENT}"
else
    echo -e "${RED}✗ Failed to create dashboard${NC}"
fi

echo ""

###############################################################################
# Dashboard 3: Data Quality & Storage
###############################################################################

echo -e "${BLUE}[3/3] Creating Data Quality Dashboard...${NC}"

aws cloudwatch put-dashboard \
  --dashboard-name "NOAA-Data-Quality-${ENVIRONMENT}" \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}" \
  --dashboard-body file://<(cat <<'DASHBOARD3'
{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 2,
      "properties": {
        "markdown": "# NOAA Data Quality & Storage\nMonitor data quality, storage, and Athena queries"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "S3 Bucket Size",
        "metrics": [
          ["AWS/S3", "BucketSizeBytes", {"stat": "Average"}]
        ],
        "period": 86400,
        "stat": "Average",
        "region": "us-east-1",
        "view": "timeSeries",
        "yAxis": {
          "left": {
            "label": "Bytes"
          }
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
        "title": "S3 Object Count",
        "metrics": [
          ["AWS/S3", "NumberOfObjects", {"stat": "Average"}]
        ],
        "period": 86400,
        "stat": "Average",
        "region": "us-east-1",
        "view": "timeSeries"
      }
    },
    {
      "type": "metric",
      "x": 16,
      "y": 2,
      "width": 8,
      "height": 6,
      "properties": {
        "title": "Athena Queries",
        "metrics": [
          ["AWS/Athena", "DataScannedInBytes", {"stat": "Sum"}]
        ],
        "period": 3600,
        "stat": "Sum",
        "region": "us-east-1",
        "view": "timeSeries",
        "yAxis": {
          "left": {
            "label": "Bytes"
          }
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
        "title": "Glue Job Runs",
        "metrics": [
          ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", {"stat": "Sum"}]
        ],
        "period": 3600,
        "stat": "Sum",
        "region": "us-east-1",
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
        "title": "Lambda Throttles",
        "metrics": [
          ["AWS/Lambda", "Throttles", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "view": "timeSeries"
      }
    }
  ]
}
DASHBOARD3
)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Data Quality Dashboard created${NC}"
    echo "  URL: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-Data-Quality-${ENVIRONMENT}"
else
    echo -e "${RED}✗ Failed to create dashboard${NC}"
fi

echo ""

###############################################################################
# Verify
###############################################################################

echo -e "${BLUE}Verifying dashboards...${NC}"

DASHBOARDS=$(aws cloudwatch list-dashboards \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}" \
    --query "DashboardEntries[?contains(DashboardName, 'NOAA')].DashboardName" \
    --output text)

if [ -n "$DASHBOARDS" ]; then
    echo -e "${GREEN}✓ Found CloudWatch dashboards:${NC}"
    echo "$DASHBOARDS" | tr '\t' '\n' | sed 's/^/  - /'
else
    echo -e "${RED}✗ No dashboards found${NC}"
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Access your dashboards at:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:"
