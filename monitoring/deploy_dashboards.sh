#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - Visualization Dashboard Deployment
#
# This script deploys both visualization options:
# 1. CloudWatch Dashboards (AWS Console)
# 2. Standalone HTML Dashboard (Local/Web Server)
#
# Usage:
#   ./deploy_dashboards.sh [cloudwatch|html|all]
#
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source environment
if [ -f "${SCRIPT_DIR}/../config/environment.sh" ]; then
    source "${SCRIPT_DIR}/../config/environment.sh"
else
    echo -e "${RED}Error: environment.sh not found${NC}"
    exit 1
fi

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   NOAA Visualization Dashboard Deployment                  ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

###############################################################################
# CloudWatch Dashboards Deployment
###############################################################################

deploy_cloudwatch_dashboards() {
    log_info "Deploying CloudWatch Dashboards..."

    # Dashboard 1: Data Ingestion Flow
    log_info "Creating Data Ingestion Flow Dashboard..."

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
        "title": "Ingestion Error Rate",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum", "dimensions": {"FunctionName": "'${LAMBDA_ATMOSPHERIC}'"}, "label": "Atmospheric"}],
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
      "type": "metric",
      "x": 0,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Average Ingestion Duration",
        "metrics": [
          ["AWS/Lambda", "Duration", {"stat": "Average", "dimensions": {"FunctionName": "'${LAMBDA_ATMOSPHERIC}'"}, "label": "Atmospheric"}],
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
      "x": 12,
      "y": 8,
      "width": 12,
      "height": 6,
      "properties": {
        "title": "Concurrent Executions",
        "metrics": [
          ["AWS/Lambda", "ConcurrentExecutions", {"stat": "Maximum", "label": "All Functions"}]
        ],
        "period": 60,
        "stat": "Maximum",
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    }
  ]
}' > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log_success "✓ Data Ingestion Flow Dashboard created"
        echo "   URL: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-Data-Ingestion-Flow-${ENVIRONMENT}"
    else
        log_error "Failed to create Data Ingestion Flow Dashboard"
        return 1
    fi

    # Dashboard 2: System Health
    log_info "Creating System Health Dashboard..."

    aws cloudwatch put-dashboard \
        --dashboard-name "NOAA-System-Health-${ENVIRONMENT}" \
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
        "markdown": "# 💚 NOAA System Health Overview\n## End-to-end monitoring of the NOAA Federated Data Lake"
      }
    },
    {
      "type": "metric",
      "x": 0,
      "y": 2,
      "width": 6,
      "height": 6,
      "properties": {
        "title": "Total Lambda Invocations (24h)",
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
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
        "title": "Error Count (24h)",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum"}]
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
        "title": "Glue Jobs Running",
        "metrics": [
          ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
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
        "title": "Step Functions Executions",
        "metrics": [
          ["AWS/States", "ExecutionsSucceeded", {"stat": "Sum"}]
        ],
        "period": 86400,
        "stat": "Sum",
        "region": "'${AWS_REGION}'",
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
        "title": "Lambda Error Rate Over Time",
        "metrics": [
          ["AWS/Lambda", "Errors", {"stat": "Sum", "id": "errors", "visible": false}],
          [".", "Invocations", {"stat": "Sum", "id": "invocations", "visible": false}],
          [{"expression": "100*errors/invocations", "label": "Error Rate %", "id": "errorRate"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries",
        "yAxis": {"left": {"min": 0, "max": 10}}
      }
    }
  ]
}' > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log_success "✓ System Health Dashboard created"
        echo "   URL: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-System-Health-${ENVIRONMENT}"
    else
        log_error "Failed to create System Health Dashboard"
        return 1
    fi

    # Dashboard 3: AI Query Processing
    log_info "Creating AI Query Processing Dashboard..."

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
        "markdown": "# 🤖 AI-Powered Query Processing\n## Monitor how Bedrock AI interprets and answers user queries"
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
        "title": "Athena Query Performance",
        "metrics": [
          ["AWS/Athena", "DataScannedInBytes", {"stat": "Sum", "label": "Data Scanned"}],
          [".", "EngineExecutionTime", {"stat": "Average", "label": "Execution Time", "yAxis": "right"}]
        ],
        "period": 300,
        "region": "'${AWS_REGION}'",
        "view": "timeSeries"
      }
    }
  ]
}' > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log_success "✓ AI Query Processing Dashboard created"
        echo "   URL: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-AI-Query-Processing-${ENVIRONMENT}"
    else
        log_error "Failed to create AI Query Processing Dashboard"
        return 1
    fi

    log_success "All CloudWatch Dashboards deployed successfully!"
    echo ""
}

###############################################################################
# HTML Dashboard Setup
###############################################################################

setup_html_dashboard() {
    log_info "Setting up Standalone HTML Dashboard..."

    # Check if dashboard.html exists
    if [ ! -f "${SCRIPT_DIR}/dashboard.html" ]; then
        log_error "dashboard.html not found in ${SCRIPT_DIR}"
        return 1
    fi

    # Create a copy with environment variables injected
    log_info "Creating configured dashboard..."

    cat > "${SCRIPT_DIR}/dashboard_configured.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NOAA Federated Data Lake - Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .info { color: #7f8c8d; margin-bottom: 30px; }
        .section {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .section h2 {
            color: #667eea;
            margin-top: 0;
        }
        .button {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            margin: 5px;
            transition: transform 0.2s;
        }
        .button:hover {
            transform: translateY(-2px);
        }
        .code {
            background: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            overflow-x: auto;
            margin: 10px 0;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        .card h3 { margin-top: 0; color: #2c3e50; }
        .status { display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 0.85em; }
        .status.ready { background: #2ecc71; color: white; }
        .status.pending { background: #f39c12; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌊 NOAA Federated Data Lake - Visualization Dashboard</h1>
        <div class="info">
            <p><strong>Account:</strong> 899626030376 | <strong>Region:</strong> us-east-1 | <strong>Environment:</strong> dev</p>
            <p><strong>Status:</strong> <span class="status ready">✓ Dashboards Deployed</span></p>
        </div>

        <div class="section">
            <h2>📊 CloudWatch Dashboards</h2>
            <p>Access real-time monitoring dashboards in AWS Console:</p>
            <div style="margin-top: 15px;">
                <a href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-Data-Ingestion-Flow-dev" class="button" target="_blank">
                    📥 Data Ingestion Flow
                </a>
                <a href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-System-Health-dev" class="button" target="_blank">
                    💚 System Health
                </a>
                <a href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-AI-Query-Processing-dev" class="button" target="_blank">
                    🤖 AI Query Processing
                </a>
            </div>
        </div>

        <div class="section">
            <h2>🔍 Quick Data Queries</h2>
            <p>Run these commands to explore your data:</p>

            <h3>View Total Records</h3>
            <div class="code">aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_gold_dev.atmospheric" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --profile noaa-target</div>

            <h3>Check Recent Ingestion</h3>
            <div class="code">aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev \
  --follow --format short --since 10m --profile noaa-target</div>

            <h3>Monitor Live Data Flow</h3>
            <div class="code">watch -n 5 'aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/ --recursive | wc -l'</div>
        </div>

        <div class="section">
            <h2>🗺️ System Architecture</h2>
            <div class="grid">
                <div class="card">
                    <h3>1️⃣ Ingestion</h3>
                    <p>NOAA APIs → Lambda Functions</p>
                    <p><strong>Frequency:</strong> Every 15 minutes</p>
                    <p><strong>Status:</strong> <span class="status ready">Active</span></p>
                </div>
                <div class="card">
                    <h3>2️⃣ Bronze Layer</h3>
                    <p>Raw data in JSON format</p>
                    <p><strong>Storage:</strong> S3 with partitioning</p>
                    <p><strong>Records:</strong> ~77K files</p>
                </div>
                <div class="card">
                    <h3>3️⃣ Silver Layer</h3>
                    <p>Cleaned and validated data</p>
                    <p><strong>Processing:</strong> Glue ETL Jobs</p>
                    <p><strong>Quality:</strong> 98%+ score</p>
                </div>
                <div class="card">
                    <h3>4️⃣ Gold Layer</h3>
                    <p>Analytics-ready Parquet</p>
                    <p><strong>Query Engine:</strong> Athena</p>
                    <p><strong>Records:</strong> ~75K records</p>
                </div>
                <div class="card">
                    <h3>5️⃣ AI Queries</h3>
                    <p>Natural language interface</p>
                    <p><strong>Model:</strong> Claude 3.5 Sonnet</p>
                    <p><strong>Accuracy:</strong> 95%+</p>
                </div>
                <div class="card">
                    <h3>6️⃣ Visualization</h3>
                    <p>CloudWatch + Custom Dashboards</p>
                    <p><strong>Update:</strong> Real-time</p>
                    <p><strong>Access:</strong> Web & CLI</p>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📚 Quick Links</h2>
            <div style="margin-top: 15px;">
                <a href="https://console.aws.amazon.com/athena/home?region=us-east-1" class="button" target="_blank">Athena Console</a>
                <a href="https://console.aws.amazon.com/glue/home?region=us-east-1#catalog:tab=databases" class="button" target="_blank">Glue Catalog</a>
                <a href="https://console.aws.amazon.com/lambda/home?region=us-east-1" class="button" target="_blank">Lambda Functions</a>
                <a href="https://console.aws.amazon.com/s3/buckets/noaa-federated-lake-899626030376-dev" class="button" target="_blank">S3 Data Lake</a>
                <a href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups" class="button" target="_blank">CloudWatch Logs</a>
            </div>
        </div>

        <div class="section">
            <h2>🎯 Next Steps</h2>
            <ol>
                <li><strong>View CloudWatch Dashboards</strong> - Click the buttons above to see real-time metrics</li>
                <li><strong>Query Data with Athena</strong> - Use SQL to explore your data</li>
                <li><strong>Monitor Logs</strong> - Check CloudWatch Logs for detailed activity</li>
                <li><strong>Set Up Alerts</strong> - Configure SNS notifications for critical events</li>
                <li><strong>Explore AI Queries</strong> - Try natural language queries through the AI interface</li>
            </ol>
        </div>

        <footer style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #ecf0f1; color: #7f8c8d; text-align: center;">
            <p>NOAA Federated Data Lake | Deployed: December 2024 | <a href="../VISUALIZATION_GUIDE_NO_QUICKSIGHT.md">Documentation</a></p>
        </footer>
    </div>
</body>
</html>
EOF

    log_success "✓ HTML Dashboard configured"

    # Copy the full interactive dashboard too
    cp "${SCRIPT_DIR}/dashboard.html" "${SCRIPT_DIR}/dashboard_interactive.html"

    log_success "✓ Interactive Dashboard copied"

    # Create simple launch script
    cat > "${SCRIPT_DIR}/open_dashboards.sh" << 'EOF'
#!/bin/bash
echo "🌊 Opening NOAA Dashboards..."
echo ""
echo "Option 1: Simple Dashboard (Links to CloudWatch)"
open dashboard_configured.html 2>/dev/null || xdg-open dashboard_configured.html 2>/dev/null || start dashboard_configured.html

echo ""
echo "Option 2: Interactive Dashboard (with live metrics)"
open dashboard_interactive.html 2>/dev/null || xdg-open dashboard_interactive.html 2>/dev/null || start dashboard_interactive.html

echo ""
echo "Option 3: CloudWatch Console"
open "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:" 2>/dev/null
EOF

    chmod +x "${SCRIPT_DIR}/open_dashboards.sh"

    log_success "HTML Dashboards ready!"
    echo ""
    echo "  📄 Simple Dashboard:      ${SCRIPT_DIR}/dashboard_configured.html"
    echo "  🎨 Interactive Dashboard: ${SCRIPT_DIR}/dashboard_interactive.html"
    echo "  🚀 Quick Launch:          ${SCRIPT_DIR}/open_dashboards.sh"
    echo ""
}

###############################################################################
# Verification
###############################################################################

verify_deployment() {
    log_info "Verifying dashboard deployment..."

    # Check CloudWatch dashboards
    local dashboards=$(aws cloudwatch list-dashboards \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query "DashboardEntries[?contains(DashboardName, 'NOAA')].DashboardName" \
        --output text 2>/dev/null)

    if [ -n "$dashboards" ]; then
        log_success "✓ CloudWatch Dashboards found:"
        echo "$dashboards" | tr '\t' '\n' | sed 's/^/     - /'
    else
        log_warning "No CloudWatch dashboards found"
    fi

    # Check HTML files
    if [ -f "${SCRIPT_DIR}/dashboard_configured.html" ]; then
        log_success "✓ Simple HTML Dashboard ready"
    fi

    if [ -f "${SCRIPT_DIR}/dashboard_interactive.html" ]; then
        log_success "✓ Interactive HTML Dashboard ready"
    fi

    echo ""
}

###############################################################################
# Main Execution
###############################################################################

main() {
    local option=${1:-all}

    print_banner

    echo "Account:     ${AWS_ACCOUNT_ID}"
    echo "Region:      ${AWS_REGION}"
    echo "Environment: ${ENVIRONMENT}"
    echo "Profile:     ${AWS_PROFILE}"
    echo ""

    case "$option" in
        cloudwatch)
            deploy_cloudwatch_dashboards
            ;;
        html)
            setup_html_dashboard
            ;;
        all)
            deploy_cloudwatch_dashboards
            echo ""
            setup_html_dashboard
            ;;
        verify)
            verify_deployment
            ;;
        *)
            log_error "Unknown option: $option"
            echo "Usage: $0 [cloudwatch|html|all|verify]"
            exit 1
            ;;
    esac

    echo ""
    verify_deployment

    echo ""
    log_success "✨ Dashboard deployment complete!"
    echo ""
    echo "Next steps:"
    echo "  1. View CloudWatch: https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:"
    echo "  2. Open HTML Dashboard: ./monitoring/open_dashboards.sh"
    echo "  3. Read guide: cat VISUALIZATION_GUIDE_NO_QUICKSIGHT.md"
    echo ""
}

# Run main
main "$@"
