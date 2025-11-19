#!/bin/bash
#
# NOAA Federated Data Lake - Webapp Deployment Script
# Version: 1.0.0
# Description: Safely deploy webapp updates to S3 and CloudFront
#
# Usage:
#   ./scripts/deploy_webapp.sh [--dry-run] [--skip-invalidation]
#
# Options:
#   --dry-run            Show what would be deployed without making changes
#   --skip-invalidation  Skip CloudFront cache invalidation (faster but old cache remains)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
S3_BUCKET="noaa-chatbot-1762359283"
CLOUDFRONT_DIST_ID="E22UXNSTO9T2DE"
CLOUDFRONT_DOMAIN="dq8oz5pgpnqc1.cloudfront.net"
WEBAPP_DIR="webapp"
BACKUP_DIR="backups/webapp-$(date +%Y%m%d-%H%M%S)"

# Parse command line arguments
DRY_RUN=false
SKIP_INVALIDATION=false
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-invalidation)
            SKIP_INVALIDATION=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--dry-run] [--skip-invalidation]"
            exit 0
            ;;
    esac
done

# Helper functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Header
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  NOAA Data Lake - Webapp Deployment"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ "$DRY_RUN" = true ]; then
    warning "DRY RUN MODE - No changes will be made"
    echo ""
fi

# Step 1: Pre-flight checks
log "Running pre-flight checks..."

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    error "AWS credentials not configured"
    exit 1
fi
success "AWS credentials valid"

# Check if webapp directory exists
if [ ! -d "$WEBAPP_DIR" ]; then
    error "Webapp directory not found: $WEBAPP_DIR"
    exit 1
fi
success "Webapp directory found"

# Check if critical files exist
CRITICAL_FILES=("$WEBAPP_DIR/index.html" "$WEBAPP_DIR/app.js")
for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Critical file not found: $file"
        exit 1
    fi
done
success "All critical files present"

# Check for JavaScript syntax errors
log "Checking JavaScript syntax..."
if command -v node &> /dev/null; then
    if node -c "$WEBAPP_DIR/app.js" 2>&1 | grep -q "SyntaxError"; then
        error "JavaScript syntax error detected in app.js"
        node -c "$WEBAPP_DIR/app.js"
        exit 1
    fi
    success "JavaScript syntax valid"
else
    warning "Node.js not found, skipping syntax check"
fi

# Check for errant HTML tags in JavaScript
if grep -q '</text>' "$WEBAPP_DIR/app.js"; then
    error "Found errant HTML tags in app.js"
    exit 1
fi
success "No HTML tags in JavaScript"

# Check S3 bucket accessibility
if ! aws s3 ls "s3://$S3_BUCKET" > /dev/null 2>&1; then
    error "Cannot access S3 bucket: $S3_BUCKET"
    exit 1
fi
success "S3 bucket accessible"

# Check CloudFront distribution status
DIST_STATUS=$(aws cloudfront get-distribution --id "$CLOUDFRONT_DIST_ID" --query 'Distribution.Status' --output text 2>&1)
if [ $? -ne 0 ]; then
    error "Cannot access CloudFront distribution: $CLOUDFRONT_DIST_ID"
    exit 1
fi
success "CloudFront distribution accessible (Status: $DIST_STATUS)"

echo ""

# Step 2: Backup current deployment
log "Creating backup of current deployment..."
mkdir -p "$BACKUP_DIR"

if [ "$DRY_RUN" = false ]; then
    # Download current files from S3
    aws s3 cp "s3://$S3_BUCKET/index.html" "$BACKUP_DIR/index.html" 2>/dev/null || warning "Could not backup index.html"
    aws s3 cp "s3://$S3_BUCKET/app.js" "$BACKUP_DIR/app.js" 2>/dev/null || warning "Could not backup app.js"

    if [ -f "$BACKUP_DIR/index.html" ]; then
        success "Backup created: $BACKUP_DIR"
        echo "  Files backed up:"
        ls -lh "$BACKUP_DIR" | tail -n +2 | awk '{print "    - " $9 " (" $5 ")"}'
    else
        warning "Backup incomplete (files may not exist in S3 yet)"
    fi
else
    echo "  [DRY RUN] Would create backup in: $BACKUP_DIR"
fi

echo ""

# Step 3: Deploy files to S3
log "Deploying files to S3..."

FILES_TO_DEPLOY=(
    "index.html:text/html"
    "app.js:text/javascript"
)

for file_info in "${FILES_TO_DEPLOY[@]}"; do
    IFS=':' read -r filename content_type <<< "$file_info"
    filepath="$WEBAPP_DIR/$filename"

    if [ ! -f "$filepath" ]; then
        warning "Skipping $filename (not found)"
        continue
    fi

    filesize=$(stat -f%z "$filepath" 2>/dev/null || stat -c%s "$filepath" 2>/dev/null)
    filesize_kb=$((filesize / 1024))

    if [ "$DRY_RUN" = false ]; then
        aws s3 cp "$filepath" "s3://$S3_BUCKET/$filename" \
            --content-type "$content_type" \
            --cache-control "no-cache, no-store, must-revalidate" \
            --metadata-directive REPLACE

        success "Deployed: $filename (${filesize_kb}KB)"
    else
        echo "  [DRY RUN] Would deploy: $filename (${filesize_kb}KB) -> s3://$S3_BUCKET/$filename"
    fi
done

echo ""

# Step 4: Invalidate CloudFront cache
if [ "$SKIP_INVALIDATION" = false ]; then
    log "Invalidating CloudFront cache..."

    if [ "$DRY_RUN" = false ]; then
        INVALIDATION_ID=$(aws cloudfront create-invalidation \
            --distribution-id "$CLOUDFRONT_DIST_ID" \
            --paths "/*" \
            --query 'Invalidation.Id' \
            --output text)

        success "CloudFront invalidation created: $INVALIDATION_ID"
        echo "  Distribution: $CLOUDFRONT_DIST_ID"
        echo "  Status: In Progress"
        warning "Cache invalidation takes 1-3 minutes to complete"
    else
        echo "  [DRY RUN] Would invalidate: $CLOUDFRONT_DIST_ID (paths: /*)"
    fi
else
    warning "Skipping CloudFront cache invalidation (may serve old files for up to 24 hours)"
fi

echo ""

# Step 5: Verification
log "Deployment verification..."

if [ "$DRY_RUN" = false ]; then
    # Wait a moment for S3 to propagate
    sleep 2

    # Verify files in S3
    echo ""
    echo "Files in S3 bucket:"
    aws s3 ls "s3://$S3_BUCKET/" --human-readable | grep -E '(index.html|app.js)' | awk '{print "  - " $4 " (" $3 ")"}'

    # Check app.js content
    echo ""
    log "Checking deployed app.js..."
    REMOTE_JS=$(curl -s "https://$CLOUDFRONT_DOMAIN/app.js?t=$(date +%s)")

    if echo "$REMOTE_JS" | grep -q "NOAA Data Lake Chatbot"; then
        success "app.js header present"
    else
        warning "app.js may not be deployed correctly"
    fi

    if echo "$REMOTE_JS" | grep -q "const CONFIG"; then
        success "CONFIG object found"
    else
        error "CONFIG object not found in deployed app.js"
    fi

    if echo "$REMOTE_JS" | grep -q "FALLBACK_PONDS"; then
        success "FALLBACK_PONDS found"
    else
        warning "FALLBACK_PONDS not found"
    fi

    if echo "$REMOTE_JS" | grep -q '</text>'; then
        error "Errant HTML tags found in deployed app.js!"
    else
        success "No errant HTML tags"
    fi

    if echo "$REMOTE_JS" | grep -q "let isResizing"; then
        success "isResizing variable declaration found"
    else
        warning "isResizing variable may not be declared"
    fi

else
    echo "  [DRY RUN] Would verify deployment"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
if [ "$DRY_RUN" = false ]; then
    echo -e "${GREEN}✓ Deployment Complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Wait 1-3 minutes for CloudFront invalidation"
    echo "  2. Open: https://$CLOUDFRONT_DOMAIN/"
    echo "  3. Force refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)"
    echo "  4. Check browser console for errors"
    echo ""
    echo "To test:"
    echo "  ./venv/bin/python tests/test_e2e_python.py https://$CLOUDFRONT_DOMAIN"
else
    echo -e "${YELLOW}Dry run complete - no changes made${NC}"
    echo ""
    echo "To deploy for real, run:"
    echo "  $0"
fi
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Create deployment log
if [ "$DRY_RUN" = false ]; then
    LOG_FILE="logs/deployment-$(date +%Y%m%d-%H%M%S).log"
    {
        echo "Deployment Log"
        echo "=============="
        echo "Date: $(date)"
        echo "User: $(whoami)"
        echo "S3 Bucket: $S3_BUCKET"
        echo "CloudFront: $CLOUDFRONT_DIST_ID"
        echo "Domain: https://$CLOUDFRONT_DOMAIN"
        echo ""
        echo "Files Deployed:"
        for file_info in "${FILES_TO_DEPLOY[@]}"; do
            IFS=':' read -r filename content_type <<< "$file_info"
            if [ -f "$WEBAPP_DIR/$filename" ]; then
                echo "  - $filename"
            fi
        done
        echo ""
        echo "Backup Location: $BACKUP_DIR"
    } > "$LOG_FILE"

    echo "Deployment log saved: $LOG_FILE"
    echo ""
fi

exit 0
