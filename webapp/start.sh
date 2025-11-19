#!/bin/bash
# NOAA Data Lake Chatbot - Startup Script
# This script starts the Flask web server for the chatbot interface

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo ""
echo "================================================================================"
echo "                   NOAA DATA LAKE - AI CHATBOT INTERFACE"
echo "================================================================================"
echo ""

# Check Python version
echo -e "${BLUE}[1/5]${NC} Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python ${PYTHON_VERSION} found"
else
    echo -e "${RED}✗${NC} Python 3 not found. Please install Python 3.9 or higher."
    exit 1
fi

# Check if virtual environment exists
echo ""
echo -e "${BLUE}[2/5]${NC} Checking virtual environment..."
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment found"
    source venv/bin/activate
else
    echo -e "${YELLOW}⚠${NC} No virtual environment found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Install dependencies
echo ""
echo -e "${BLUE}[3/5]${NC} Checking dependencies..."
if pip show flask &> /dev/null; then
    echo -e "${GREEN}✓${NC} Dependencies already installed"
else
    echo -e "${YELLOW}⚠${NC} Installing dependencies..."
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Dependencies installed"
fi

# Check configuration
echo ""
echo -e "${BLUE}[4/5]${NC} Checking configuration..."
if [ -z "$API_GATEWAY_URL" ]; then
    echo -e "${YELLOW}⚠${NC} API_GATEWAY_URL not set"
    echo -e "   ${YELLOW}→${NC} Running in LOCAL mode (using Lambda handlers directly)"
    echo -e "   ${YELLOW}→${NC} To use PROXY mode, set: export API_GATEWAY_URL='your-url'"
else
    echo -e "${GREEN}✓${NC} API_GATEWAY_URL configured"
    echo -e "   ${GREEN}→${NC} Running in PROXY mode"
    echo -e "   ${GREEN}→${NC} API Gateway: ${API_GATEWAY_URL}"
fi

# Check for CDO token
if [ -z "$NOAA_CDO_TOKEN" ]; then
    echo -e "${YELLOW}⚠${NC} NOAA_CDO_TOKEN not set (optional)"
    echo -e "   ${YELLOW}→${NC} Climate Data Online API will not be available"
else
    echo -e "${GREEN}✓${NC} NOAA_CDO_TOKEN configured"
fi

# Set default port if not specified
if [ -z "$PORT" ]; then
    export PORT=5000
fi

# Start server
echo ""
echo -e "${BLUE}[5/5]${NC} Starting Flask server..."
echo ""
echo "================================================================================"
echo -e "${GREEN}🚀 Server starting on http://localhost:${PORT}${NC}"
echo "================================================================================"
echo ""
echo "Available endpoints:"
echo -e "  ${GREEN}→${NC} Chatbot UI:    http://localhost:${PORT}"
echo -e "  ${GREEN}→${NC} Health Check:  http://localhost:${PORT}/api/health"
echo -e "  ${GREEN}→${NC} System Stats:  http://localhost:${PORT}/api/stats"
echo ""
echo "Quick tips:"
echo -e "  ${BLUE}•${NC} Press Ctrl+C to stop the server"
echo -e "  ${BLUE}•${NC} Set DEBUG=True for verbose logging"
echo -e "  ${BLUE}•${NC} Configure API_GATEWAY_URL for production mode"
echo ""
echo "================================================================================"
echo ""

# Start the server
python3 server.py

# This runs when the server stops
echo ""
echo -e "${YELLOW}Server stopped${NC}"
echo ""
