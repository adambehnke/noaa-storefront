#!/bin/bash
# NOAA Data Lake Chatbot - AWS Deployment Script
# This script deploys the chatbot to AWS using CloudFormation, S3, and CloudFront

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="noaa-chatbot"
ENVIRONMENT="prod"
AWS_REGION="us-east-1"

# Print banner
echo ""
echo "================================================================================"
echo -e "${CYAN}              NOAA DATA LAKE CHATBOT - AWS DEPLOYMENT${NC}"
echo "================================================================================"
echo ""

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
print_status "Checking prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install it first."
    echo "Visit: https://aws.amazon.com/cli/"
    exit 1
fi

print_success "AWS CLI found: $(aws --version)"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured."
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_success "AWS credentials configured for account: $ACCOUNT_ID"

# Get API Gateway URL
echo ""
print_status "Looking for existing API Gateway..."

API_GATEWAY_URL=""

# Try to find the API Gateway from existing stacks
EXISTING_STACKS=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --region $AWS_REGION --query 'StackSummaries[?contains(StackName, `noaa`)].StackName' --output text)

for stack in $EXISTING_STACKS; do
    URL=$(aws cloudformation describe-stacks --stack-name $stack --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' --output text 2>/dev/null || echo "")
    if [ ! -z "$URL" ]; then
        API_GATEWAY_URL=$URL
        print_success "Found API Gateway URL from stack '$stack': $API_GATEWAY_URL"
        break
    fi
done

# If not found, ask user
if [ -z "$API_GATEWAY_URL" ]; then
    print_warning "API Gateway URL not found in existing stacks."
    echo ""
    read -p "Enter your API Gateway URL (e.g., https://abc123.execute-api.us-east-1.amazonaws.com/dev): " API_GATEWAY_URL

    if [ -z "$API_GATEWAY_URL" ]; then
        print_error "API Gateway URL is required for deployment."
        exit 1
    fi
fi

# Validate API Gateway URL format
if [[ ! $API_GATEWAY_URL =~ ^https://.* ]]; then
    print_error "Invalid API Gateway URL format. Must start with https://"
    exit 1
fi

print_success "Using API Gateway URL: $API_GATEWAY_URL"

# Optional: Custom domain and certificate
echo ""
read -p "Do you have a custom domain? (y/N): " HAS_DOMAIN
CUSTOM_DOMAIN=""
CERTIFICATE_ARN=""

if [[ $HAS_DOMAIN =~ ^[Yy]$ ]]; then
    read -p "Enter custom domain (e.g., chatbot.yourdomain.com): " CUSTOM_DOMAIN
    read -p "Enter ACM Certificate ARN (must be in us-east-1): " CERTIFICATE_ARN
fi

# Optional: Enable WAF
echo ""
read -p "Enable AWS WAF for DDoS protection? (y/N): " ENABLE_WAF
WAF_ENABLED="false"
if [[ $ENABLE_WAF =~ ^[Yy]$ ]]; then
    WAF_ENABLED="true"
fi

# Update app.js with API Gateway URL
echo ""
print_status "Updating app.js with API Gateway URL..."

cd "$(dirname "$0")"

# Create a temporary app.js with updated URL
sed "s|API_BASE_URL: 'https://your-api-gateway.*amazonaws.com/dev'|API_BASE_URL: '$API_GATEWAY_URL'|g" app.js > app.js.tmp
mv app.js.tmp app.js

print_success "app.js updated with API Gateway URL"

# Deploy CloudFormation stack
echo ""
print_status "Deploying CloudFormation stack..."
print_status "Stack Name: $STACK_NAME-$ENVIRONMENT"
print_status "Region: $AWS_REGION"

PARAMS="ParameterKey=ProjectName,ParameterValue=$STACK_NAME \
ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
ParameterKey=ApiGatewayUrl,ParameterValue=$API_GATEWAY_URL \
ParameterKey=EnableWAF,ParameterValue=$WAF_ENABLED"

if [ ! -z "$CUSTOM_DOMAIN" ]; then
    PARAMS="$PARAMS ParameterKey=DomainName,ParameterValue=$CUSTOM_DOMAIN"
fi

if [ ! -z "$CERTIFICATE_ARN" ]; then
    PARAMS="$PARAMS ParameterKey=CertificateArn,ParameterValue=$CERTIFICATE_ARN"
fi

aws cloudformation deploy \
    --template-file deploy-to-aws.yaml \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --parameter-overrides $PARAMS \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $AWS_REGION \
    --no-fail-on-empty-changeset

if [ $? -eq 0 ]; then
    print_success "CloudFormation stack deployed successfully"
else
    print_error "CloudFormation deployment failed"
    exit 1
fi

# Get stack outputs
echo ""
print_status "Retrieving stack outputs..."

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
    --output text)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text)

WEBSITE_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME-$ENVIRONMENT" \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
    --output text)

print_success "S3 Bucket: $BUCKET_NAME"
print_success "CloudFront Distribution: $DISTRIBUTION_ID"
print_success "Website URL: $WEBSITE_URL"

# Upload files to S3
echo ""
print_status "Uploading files to S3..."

# Upload HTML (no cache)
aws s3 cp index.html "s3://$BUCKET_NAME/" \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate" \
    --region $AWS_REGION

# Upload JS (versioned, long cache)
aws s3 cp app.js "s3://$BUCKET_NAME/" \
    --content-type "application/javascript" \
    --cache-control "public, max-age=31536000, immutable" \
    --region $AWS_REGION

print_success "Files uploaded to S3"

# Create invalidation
echo ""
print_status "Invalidating CloudFront cache..."

INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id $DISTRIBUTION_ID \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text)

print_success "CloudFront invalidation created: $INVALIDATION_ID"
print_status "Waiting for invalidation to complete (this may take a few minutes)..."

aws cloudfront wait invalidation-completed \
    --distribution-id $DISTRIBUTION_ID \
    --id $INVALIDATION_ID

print_success "CloudFront cache invalidated"

# Test the deployment
echo ""
print_status "Testing deployment..."

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$WEBSITE_URL")

if [ "$HTTP_STATUS" -eq 200 ]; then
    print_success "Website is responding (HTTP $HTTP_STATUS)"
else
    print_warning "Website returned HTTP $HTTP_STATUS"
fi

# Print summary
echo ""
echo "================================================================================"
echo -e "${GREEN}                    DEPLOYMENT SUCCESSFUL!${NC}"
echo "================================================================================"
echo ""
echo -e "${CYAN}Website URL:${NC}"
echo "  $WEBSITE_URL"
echo ""
echo -e "${CYAN}CloudFront Distribution:${NC}"
echo "  $DISTRIBUTION_ID"
echo ""
echo -e "${CYAN}S3 Bucket:${NC}"
echo "  $BUCKET_NAME"
echo ""
echo -e "${CYAN}API Gateway:${NC}"
echo "  $API_GATEWAY_URL"
echo ""

if [ ! -z "$CUSTOM_DOMAIN" ]; then
    echo -e "${CYAN}Custom Domain:${NC}"
    echo "  $CUSTOM_DOMAIN"
    echo ""
    echo -e "${YELLOW}Note:${NC} Update your DNS records to point to:"
    echo "  $(aws cloudformation describe-stacks --stack-name "$STACK_NAME-$ENVIRONMENT" --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomainName`].OutputValue' --output text)"
    echo ""
fi

echo -e "${CYAN}Next Steps:${NC}"
echo "  1. Visit $WEBSITE_URL to access the chatbot"
echo "  2. Test queries in different data ponds"
echo "  3. Monitor CloudWatch metrics"
echo "  4. Set up SNS alerts (optional)"
echo ""

if [ "$WAF_ENABLED" = "true" ]; then
    echo -e "${GREEN}✓${NC} AWS WAF enabled for DDoS protection"
else
    echo -e "${YELLOW}⚠${NC} AWS WAF not enabled. Consider enabling for production."
fi

echo ""
echo -e "${CYAN}Management Commands:${NC}"
echo ""
echo "  # View CloudWatch logs"
echo "  aws logs tail /aws/cloudfront/$DISTRIBUTION_ID --follow --region us-east-1"
echo ""
echo "  # Update deployment (after changes)"
echo "  ./deploy-chatbot.sh"
echo ""
echo "  # Delete stack (cleanup)"
echo "  aws cloudformation delete-stack --stack-name $STACK_NAME-$ENVIRONMENT --region $AWS_REGION"
echo ""
echo "================================================================================"
echo ""

# Save deployment info
cat > deployment-info.json <<EOF
{
  "stack_name": "$STACK_NAME-$ENVIRONMENT",
  "region": "$AWS_REGION",
  "bucket_name": "$BUCKET_NAME",
  "distribution_id": "$DISTRIBUTION_ID",
  "website_url": "$WEBSITE_URL",
  "api_gateway_url": "$API_GATEWAY_URL",
  "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "account_id": "$ACCOUNT_ID"
}
EOF

print_success "Deployment info saved to deployment-info.json"

exit 0
