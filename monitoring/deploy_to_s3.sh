#!/bin/bash
###############################################################################
# NOAA Dashboard Deployment to S3 + CloudFront
#
# This script deploys a fully hosted dashboard solution on AWS:
# - Creates S3 bucket for hosting
# - Sets up CloudFront CDN for HTTPS access
# - Deploys Lambda function for real-time data API
# - Uploads all dashboard HTML files
#
# Usage:
#   ./deploy_to_s3.sh [deploy|upload|update|delete]
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

# Load environment
if [ -f "${SCRIPT_DIR}/../config/environment.sh" ]; then
    source "${SCRIPT_DIR}/../config/environment.sh"
else
    echo -e "${RED}Error: environment.sh not found${NC}"
    exit 1
fi

# Stack name
STACK_NAME="noaa-dashboard-hosting-${ENVIRONMENT}"

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
    echo -e "${BLUE}║   NOAA Dashboard Deployment to S3 + CloudFront            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

###############################################################################
# Deploy CloudFormation Stack
###############################################################################

deploy_stack() {
    log_info "Deploying CloudFormation stack..."

    if ! [ -f "${SCRIPT_DIR}/dashboard-hosting.yaml" ]; then
        log_error "CloudFormation template not found: dashboard-hosting.yaml"
        return 1
    fi

    # Check if stack exists
    if aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" &>/dev/null; then
        log_info "Stack exists. Updating..."

        aws cloudformation update-stack \
            --stack-name "${STACK_NAME}" \
            --template-body "file://${SCRIPT_DIR}/dashboard-hosting.yaml" \
            --parameters \
                ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
                ParameterKey=AccountId,ParameterValue=${AWS_ACCOUNT_ID} \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}" 2>&1 | tee /tmp/stack-output.txt

        if grep -q "No updates are to be performed" /tmp/stack-output.txt; then
            log_warning "No updates needed"
            return 0
        fi

        log_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "${STACK_NAME}" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    else
        log_info "Creating new stack..."

        aws cloudformation create-stack \
            --stack-name "${STACK_NAME}" \
            --template-body "file://${SCRIPT_DIR}/dashboard-hosting.yaml" \
            --parameters \
                ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
                ParameterKey=AccountId,ParameterValue=${AWS_ACCOUNT_ID} \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"

        log_info "Waiting for stack creation to complete (this takes 5-10 minutes)..."
        aws cloudformation wait stack-create-complete \
            --stack-name "${STACK_NAME}" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    fi

    log_success "Stack deployed successfully"
    return 0
}

###############################################################################
# Upload Dashboard Files
###############################################################################

upload_dashboards() {
    log_info "Uploading dashboard files to S3..."

    # Get bucket name from stack outputs
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`DashboardBucketName`].OutputValue' \
        --output text)

    if [ -z "$BUCKET_NAME" ]; then
        log_error "Could not retrieve bucket name from stack"
        return 1
    fi

    log_info "Bucket: ${BUCKET_NAME}"

    # Upload HTML files
    log_info "Uploading HTML dashboards..."
    aws s3 cp "${SCRIPT_DIR}/dashboard_configured.html" \
        "s3://${BUCKET_NAME}/" \
        --content-type "text/html" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}"

    aws s3 cp "${SCRIPT_DIR}/dashboard_interactive.html" \
        "s3://${BUCKET_NAME}/" \
        --content-type "text/html" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}"

    if [ -f "${SCRIPT_DIR}/dashboard_comprehensive.html" ]; then
        aws s3 cp "${SCRIPT_DIR}/dashboard_comprehensive.html" \
            "s3://${BUCKET_NAME}/" \
            --content-type "text/html" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    fi

    # Upload any additional assets
    if [ -d "${SCRIPT_DIR}/assets" ]; then
        log_info "Uploading assets..."
        aws s3 sync "${SCRIPT_DIR}/assets/" \
            "s3://${BUCKET_NAME}/assets/" \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    fi

    log_success "Dashboards uploaded successfully"
    return 0
}

###############################################################################
# Invalidate CloudFront Cache
###############################################################################

invalidate_cache() {
    log_info "Invalidating CloudFront cache..."

    DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
        --output text)

    if [ -z "$DISTRIBUTION_ID" ]; then
        log_warning "Could not retrieve CloudFront distribution ID"
        return 1
    fi

    aws cloudfront create-invalidation \
        --distribution-id "${DISTRIBUTION_ID}" \
        --paths "/*" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" &>/dev/null

    log_success "CloudFront cache invalidated"
    return 0
}

###############################################################################
# Show Stack Outputs
###############################################################################

show_outputs() {
    log_info "Retrieving deployment information..."

    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                    Deployment Complete                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Get all outputs
    CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionURL`].OutputValue' \
        --output text)

    ACCESS_URL=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`AccessURL`].OutputValue' \
        --output text)

    API_URL=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`DashboardDataAPIUrl`].OutputValue' \
        --output text)

    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`DashboardBucketName`].OutputValue' \
        --output text)

    echo "📊 Dashboard URLs:"
    echo ""
    echo "  Simple Dashboard:"
    echo "  ${ACCESS_URL}"
    echo ""
    echo "  Interactive Dashboard:"
    echo "  ${CLOUDFRONT_URL}/dashboard_interactive.html"
    echo ""
    echo "  Comprehensive Dashboard:"
    echo "  ${CLOUDFRONT_URL}/dashboard_comprehensive.html"
    echo ""
    echo "🔗 CloudFront Distribution:"
    echo "  ${CLOUDFRONT_URL}"
    echo ""
    echo "🌐 API Endpoint:"
    echo "  ${API_URL}"
    echo ""
    echo "📦 S3 Bucket:"
    echo "  ${BUCKET_NAME}"
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  Access your dashboards now at the URLs above             ║"
    echo "║  Share these URLs with your team for instant access       ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Save URLs to file
    cat > "${SCRIPT_DIR}/dashboard_urls.txt" <<EOF
NOAA Dashboard URLs
===================

Simple Dashboard:
${ACCESS_URL}

Interactive Dashboard:
${CLOUDFRONT_URL}/dashboard_interactive.html

Comprehensive Dashboard:
${CLOUDFRONT_URL}/dashboard_comprehensive.html

CloudFront Distribution:
${CLOUDFRONT_URL}

API Endpoint:
${API_URL}

S3 Bucket:
${BUCKET_NAME}

Deployed: $(date)
EOF

    log_success "URLs saved to: ${SCRIPT_DIR}/dashboard_urls.txt"
}

###############################################################################
# Delete Stack
###############################################################################

delete_stack() {
    log_warning "Deleting stack and all resources..."

    # Get bucket name
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'Stacks[0].Outputs[?OutputKey==`DashboardBucketName`].OutputValue' \
        --output text 2>/dev/null)

    if [ -n "$BUCKET_NAME" ]; then
        log_info "Emptying S3 bucket: ${BUCKET_NAME}"
        aws s3 rm "s3://${BUCKET_NAME}" --recursive \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}"
    fi

    log_info "Deleting CloudFormation stack..."
    aws cloudformation delete-stack \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}"

    log_info "Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete \
        --stack-name "${STACK_NAME}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}"

    log_success "Stack deleted successfully"
}

###############################################################################
# Main Execution
###############################################################################

main() {
    local action=${1:-deploy}

    print_banner

    echo "Account:     ${AWS_ACCOUNT_ID}"
    echo "Region:      ${AWS_REGION}"
    echo "Environment: ${ENVIRONMENT}"
    echo "Profile:     ${AWS_PROFILE}"
    echo ""

    case "$action" in
        deploy)
            log_info "Full deployment: Stack + Upload + Cache Invalidation"
            deploy_stack
            sleep 5
            upload_dashboards
            invalidate_cache
            show_outputs
            ;;
        upload)
            log_info "Uploading dashboards only"
            upload_dashboards
            invalidate_cache
            show_outputs
            ;;
        update)
            log_info "Updating stack and dashboards"
            deploy_stack
            sleep 5
            upload_dashboards
            invalidate_cache
            show_outputs
            ;;
        delete)
            delete_stack
            ;;
        outputs|info)
            show_outputs
            ;;
        *)
            log_error "Unknown action: $action"
            echo ""
            echo "Usage: $0 [deploy|upload|update|delete|info]"
            echo ""
            echo "Actions:"
            echo "  deploy  - Deploy CloudFormation stack and upload dashboards"
            echo "  upload  - Upload dashboards only (stack must exist)"
            echo "  update  - Update stack and re-upload dashboards"
            echo "  delete  - Delete stack and all resources"
            echo "  info    - Show deployment URLs and information"
            echo ""
            exit 1
            ;;
    esac

    echo ""
    log_success "Operation complete!"
    echo ""
}

# Run main
main "$@"
