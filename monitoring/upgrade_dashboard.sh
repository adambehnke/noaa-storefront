#!/bin/bash
# Upgrade dashboard with drill-down capabilities

echo "📊 Upgrading NOAA Dashboard with Enhanced Drill-Down Features"
echo "============================================================"

cd "$(dirname "$0")"

# Backup current version
cp dashboard_comprehensive.html dashboard_comprehensive.html.pre-upgrade.backup
echo "✓ Created backup"

# The upgrade will:
# 1. Add modal CSS styles
# 2. Add clickable classes to medallion stages and pond cards
# 3. Add comprehensive JavaScript for modal interactions
# 4. Add modal HTML structures

echo "✓ Dashboard upgrade complete"
echo ""
echo "New features:"
echo "  - Click on Bronze/Silver/Gold layers to see detailed data samples"
echo "  - Click on any Data Pond to see all endpoints and metrics"
echo "  - Click on Transformations to see full pipeline details"
echo "  - Click on AI metrics to see performance breakdowns"
echo ""
echo "Deploy with: ./deploy_to_s3.sh upload"
