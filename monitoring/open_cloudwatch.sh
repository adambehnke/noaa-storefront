#!/bin/bash
###############################################################################
# Open All NOAA CloudWatch Dashboards
###############################################################################

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

REGION="us-east-1"
ENV="dev"

echo -e "${BLUE}🌊 Opening NOAA CloudWatch Dashboards...${NC}"
echo ""

# Dashboard URLs
DASHBOARDS=(
    "NOAA-System-Health-${ENV}|System Health (Start Here!)"
    "NOAA-Data-Ingestion-Flow-${ENV}|Data Ingestion Flow"
    "NOAA-AI-Query-Processing-${ENV}|AI Query Processing"
    "NOAA-Data-Quality-${ENV}|Data Quality & Storage"
    "NOAA-DataLake-Health-${ENV}|DataLake Health"
)

# Open each dashboard
for dashboard in "${DASHBOARDS[@]}"; do
    IFS='|' read -r name display <<< "$dashboard"
    url="https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:name=${name}"

    echo -e "${GREEN}📊 Opening: ${display}${NC}"
    echo "   ${url}"

    # Open in browser (cross-platform)
    if command -v open &> /dev/null; then
        # macOS
        open "$url"
    elif command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open "$url"
    elif command -v start &> /dev/null; then
        # Windows
        start "$url"
    else
        echo "   Copy and paste the URL above into your browser"
    fi

    # Small delay between opens
    sleep 0.5
done

echo ""
echo -e "${BLUE}✨ All dashboards opened!${NC}"
echo ""
echo "📖 Dashboard List URL:"
echo "https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards:"
echo ""
echo "💡 Tip: Bookmark these URLs for quick access!"
