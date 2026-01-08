#!/bin/bash
###############################################################################
# Deploy Dashboard Metrics Lambda Function
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Deploying Dashboard Metrics Lambda Function              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Configuration
FUNCTION_NAME="noaa-dashboard-metrics"
RUNTIME="python3.11"
TIMEOUT=60
MEMORY=512
AWS_PROFILE="noaa-target"
AWS_REGION="us-east-1"
ACCOUNT_ID="899626030376"
DATA_LAKE_BUCKET="noaa-federated-lake-${ACCOUNT_ID}-dev"
ATHENA_DATABASE="noaa_data_lake"

# Check if Lambda directory exists
if [ ! -d "lambda" ]; then
    echo -e "${RED}Error: lambda directory not found${NC}"
    exit 1
fi

cd lambda

# Package Lambda function
echo -e "${YELLOW}📦 Packaging Lambda function...${NC}"
zip -q dashboard_metrics.zip dashboard_metrics.py
echo -e "${GREEN}✓ Package created${NC}"

# Check if function exists
FUNCTION_EXISTS=$(aws lambda get-function \
    --function-name ${FUNCTION_NAME} \
    --profile ${AWS_PROFILE} \
    --region ${AWS_REGION} \
    2>/dev/null || echo "")

if [ -z "$FUNCTION_EXISTS" ]; then
    echo -e "${YELLOW}📤 Creating Lambda function...${NC}"
    
    # You'll need to create or specify an IAM role
    echo -e "${YELLOW}Note: You need to provide an IAM role ARN${NC}"
    echo -e "${YELLOW}Typically: arn:aws:iam::${ACCOUNT_ID}:role/lambda-execution-role${NC}"
    echo -e "${YELLOW}This role needs permissions for: S3, Athena, Glue, CloudWatch, Lambda${NC}"
    echo ""
    read -p "Enter IAM Role ARN: " ROLE_ARN
    
    aws lambda create-function \
        --function-name ${FUNCTION_NAME} \
        --runtime ${RUNTIME} \
        --handler dashboard_metrics.lambda_handler \
        --zip-file fileb://dashboard_metrics.zip \
        --timeout ${TIMEOUT} \
        --memory-size ${MEMORY} \
        --role ${ROLE_ARN} \
        --environment Variables="{DATA_LAKE_BUCKET=${DATA_LAKE_BUCKET},ATHENA_DATABASE=${ATHENA_DATABASE},ATHENA_OUTPUT_BUCKET=s3://${DATA_LAKE_BUCKET}/athena-results/}" \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION}
    
    echo -e "${GREEN}✓ Function created${NC}"
else
    echo -e "${YELLOW}📤 Updating Lambda function code...${NC}"
    
    aws lambda update-function-code \
        --function-name ${FUNCTION_NAME} \
        --zip-file fileb://dashboard_metrics.zip \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION}
    
    echo -e "${GREEN}✓ Function updated${NC}"
    
    # Update configuration
    echo -e "${YELLOW}⚙️  Updating function configuration...${NC}"
    aws lambda update-function-configuration \
        --function-name ${FUNCTION_NAME} \
        --timeout ${TIMEOUT} \
        --memory-size ${MEMORY} \
        --environment Variables="{DATA_LAKE_BUCKET=${DATA_LAKE_BUCKET},ATHENA_DATABASE=${ATHENA_DATABASE},ATHENA_OUTPUT_BUCKET=s3://${DATA_LAKE_BUCKET}/athena-results/}" \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION}
    
    echo -e "${GREEN}✓ Configuration updated${NC}"
fi

# Check/Create Function URL
echo -e "${YELLOW}🔗 Setting up Function URL...${NC}"

URL_CONFIG=$(aws lambda get-function-url-config \
    --function-name ${FUNCTION_NAME} \
    --profile ${AWS_PROFILE} \
    --region ${AWS_REGION} \
    2>/dev/null || echo "")

if [ -z "$URL_CONFIG" ]; then
    aws lambda create-function-url-config \
        --function-name ${FUNCTION_NAME} \
        --auth-type NONE \
        --cors AllowOrigins="*",AllowMethods="GET,POST",MaxAge=3600 \
        --profile ${AWS_PROFILE} \
        --region ${AWS_REGION}
    
    echo -e "${GREEN}✓ Function URL created${NC}"
else
    echo -e "${GREEN}✓ Function URL already exists${NC}"
fi

# Get Function URL
FUNCTION_URL=$(aws lambda get-function-url-config \
    --function-name ${FUNCTION_NAME} \
    --profile ${AWS_PROFILE} \
    --region ${AWS_REGION} \
    --query 'FunctionUrl' \
    --output text)

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ Lambda Function Deployed Successfully                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Function URL:${NC}"
echo -e "${GREEN}${FUNCTION_URL}${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update monitoring/dashboard-dynamic.js with this URL:"
echo "   const METRICS_API_ENDPOINT = '${FUNCTION_URL}metrics';"
echo ""
echo "2. Redeploy dashboard:"
echo "   cd .."
echo "   ./deploy_to_s3.sh upload"
echo ""
echo "3. Test the dashboard at:"
echo "   https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html"
echo ""

# Clean up
rm dashboard_metrics.zip

cd ..
