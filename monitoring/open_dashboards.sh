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
