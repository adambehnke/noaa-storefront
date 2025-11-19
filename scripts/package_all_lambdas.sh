#!/bin/bash
###############################################################################
# Package All Lambda Functions for NOAA Federated Data Lake
#
# This script packages all Lambda functions with their dependencies and
# prepares them for deployment to AWS.
#
# Usage:
#   ./package_all_lambdas.sh [--env dev] [--upload] [--bucket BUCKET_NAME]
#
# Options:
#   --env       Environment (dev/staging/prod) - default: dev
#   --upload    Upload packages to S3
#   --bucket    S3 bucket for deployment packages
#   --clean     Clean build artifacts before packaging
###############################################################################

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
ENV="dev"
UPLOAD=false
CLEAN=false
BUCKET=""
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGE_DIR="$PROJECT_ROOT/lambda-packages"
LOG_FILE="$PROJECT_ROOT/logs/packaging_$(date +%Y%m%d_%H%M%S).log"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --upload)
            UPLOAD=true
            shift
            ;;
        --bucket)
            BUCKET="$2"
            shift 2
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# If bucket not specified, use default naming convention
if [ -z "$BUCKET" ]; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    BUCKET="noaa-deployment-packages-${ACCOUNT_ID}-${ENV}"
fi

# Create directories
mkdir -p "$PACKAGE_DIR"
mkdir -p "$PROJECT_ROOT/logs"

# Log function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${BLUE}========================================${NC}"
log "${BLUE}NOAA Lambda Function Packaging${NC}"
log "${BLUE}========================================${NC}"
log "Environment: $ENV"
log "Package Directory: $PACKAGE_DIR"
log "Upload to S3: $UPLOAD"
if [ "$UPLOAD" = true ]; then
    log "S3 Bucket: $BUCKET"
fi
log "${BLUE}========================================${NC}\n"

# Clean if requested
if [ "$CLEAN" = true ]; then
    log "${YELLOW}Cleaning existing packages...${NC}"
    rm -rf "$PACKAGE_DIR"/*
    log "${GREEN}✓ Clean complete${NC}\n"
fi

# Lambda functions to package
declare -A LAMBDA_FUNCTIONS=(
    ["ingest-oceanic"]="lambda-ingest-oceanic"
    ["ingest-atmospheric"]="lambda-ingest-atmospheric"
    ["ingest-climate"]="lambda-ingest-climate"
    ["ingest-spatial"]="lambda-ingest-spatial"
    ["ingest-terrestrial"]="lambda-ingest-terrestrial"
    ["ingest-buoy"]="lambda-ingest-buoy"
    ["enhanced-handler"]="lambda-enhanced-handler"
    ["intelligent-orchestrator"]="intelligent-orchestrator-package"
)

# Package individual Lambda function
package_lambda() {
    local FUNCTION_NAME=$1
    local SOURCE_DIR=$2

    log "${BLUE}Packaging: ${FUNCTION_NAME}${NC}"

    local WORK_DIR="$PACKAGE_DIR/$FUNCTION_NAME"
    local ZIP_FILE="$PACKAGE_DIR/${FUNCTION_NAME}.zip"

    # Create working directory
    mkdir -p "$WORK_DIR"

    # Check if source directory exists
    if [ ! -d "$PROJECT_ROOT/$SOURCE_DIR" ]; then
        log "${RED}✗ Source directory not found: $SOURCE_DIR${NC}"
        return 1
    fi

    # Copy source files
    log "  Copying source files..."
    cp -r "$PROJECT_ROOT/$SOURCE_DIR"/* "$WORK_DIR/" 2>/dev/null || true

    # Check if requirements.txt exists
    if [ -f "$PROJECT_ROOT/$SOURCE_DIR/requirements.txt" ]; then
        log "  Installing dependencies from requirements.txt..."
        pip install -q -r "$PROJECT_ROOT/$SOURCE_DIR/requirements.txt" -t "$WORK_DIR/" --upgrade
    else
        # Install common dependencies for ingestion functions
        if [[ $FUNCTION_NAME == *"ingest"* ]]; then
            log "  Installing common dependencies..."
            pip install -q -t "$WORK_DIR/" boto3 requests pandas --upgrade
        fi
    fi

    # Rename main script to lambda_function.py if needed
    if [ -f "$WORK_DIR/${FUNCTION_NAME##*-}_ingest.py" ]; then
        log "  Renaming main script to lambda_function.py..."
        mv "$WORK_DIR/${FUNCTION_NAME##*-}_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/oceanic_ingest.py" ]; then
        mv "$WORK_DIR/oceanic_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/quick_ocean_ingest.py" ]; then
        mv "$WORK_DIR/quick_ocean_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/atmospheric_ingest.py" ]; then
        mv "$WORK_DIR/atmospheric_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/climate_ingest.py" ]; then
        mv "$WORK_DIR/climate_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/spatial_ingest.py" ]; then
        mv "$WORK_DIR/spatial_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/terrestrial_ingest.py" ]; then
        mv "$WORK_DIR/terrestrial_ingest.py" "$WORK_DIR/lambda_function.py"
    elif [ -f "$WORK_DIR/buoy_ingest.py" ]; then
        mv "$WORK_DIR/buoy_ingest.py" "$WORK_DIR/lambda_function.py"
    fi

    # Ensure lambda_function.py has lambda_handler
    if [ -f "$WORK_DIR/lambda_function.py" ]; then
        if ! grep -q "def lambda_handler" "$WORK_DIR/lambda_function.py"; then
            log "${YELLOW}  Warning: lambda_handler function not found, adding wrapper...${NC}"
            cat >> "$WORK_DIR/lambda_function.py" << 'EOF'

def lambda_handler(event, context):
    """AWS Lambda handler wrapper"""
    import sys
    sys.argv = ['lambda_function.py', '--env', 'dev']
    if 'env' in event:
        sys.argv = ['lambda_function.py', '--env', event['env']]
    try:
        main()
        return {
            'statusCode': 200,
            'body': 'Ingestion completed successfully'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
EOF
        fi
    fi

    # Clean up unnecessary files
    log "  Cleaning up..."
    find "$WORK_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$WORK_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find "$WORK_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find "$WORK_DIR" -name "*.pyc" -delete 2>/dev/null || true

    # Create ZIP package
    log "  Creating ZIP package..."
    cd "$WORK_DIR"
    zip -q -r "$ZIP_FILE" . -x "*.git*" "*.DS_Store" "*__pycache__*"
    cd - > /dev/null

    # Get file size
    SIZE=$(du -h "$ZIP_FILE" | cut -f1)

    log "${GREEN}✓ Package created: ${FUNCTION_NAME}.zip ($SIZE)${NC}\n"

    # Clean up work directory
    rm -rf "$WORK_DIR"

    return 0
}

# Package all Lambda functions
TOTAL=${#LAMBDA_FUNCTIONS[@]}
SUCCESS=0
FAILED=0

log "${BLUE}Starting packaging of $TOTAL Lambda functions...${NC}\n"

for FUNCTION_NAME in "${!LAMBDA_FUNCTIONS[@]}"; do
    SOURCE_DIR="${LAMBDA_FUNCTIONS[$FUNCTION_NAME]}"

    if package_lambda "$FUNCTION_NAME" "$SOURCE_DIR"; then
        ((SUCCESS++))
    else
        ((FAILED++))
        log "${RED}✗ Failed to package: $FUNCTION_NAME${NC}\n"
    fi
done

log "${BLUE}========================================${NC}"
log "${BLUE}Packaging Summary${NC}"
log "${BLUE}========================================${NC}"
log "Total functions: $TOTAL"
log "${GREEN}Successfully packaged: $SUCCESS${NC}"
if [ $FAILED -gt 0 ]; then
    log "${RED}Failed: $FAILED${NC}"
fi
log "${BLUE}========================================${NC}\n"

# Upload to S3 if requested
if [ "$UPLOAD" = true ]; then
    log "${BLUE}Uploading packages to S3...${NC}\n"

    # Create bucket if it doesn't exist
    if ! aws s3 ls "s3://$BUCKET" 2>/dev/null; then
        log "Creating S3 bucket: $BUCKET"
        aws s3 mb "s3://$BUCKET" --region us-east-1
    fi

    # Upload each package
    UPLOAD_SUCCESS=0
    for ZIP_FILE in "$PACKAGE_DIR"/*.zip; do
        if [ -f "$ZIP_FILE" ]; then
            FILENAME=$(basename "$ZIP_FILE")
            log "  Uploading $FILENAME..."

            if aws s3 cp "$ZIP_FILE" "s3://$BUCKET/lambda-packages/$FILENAME" --quiet; then
                log "${GREEN}  ✓ Uploaded: $FILENAME${NC}"
                ((UPLOAD_SUCCESS++))
            else
                log "${RED}  ✗ Failed to upload: $FILENAME${NC}"
            fi
        fi
    done

    log "\n${GREEN}✓ Uploaded $UPLOAD_SUCCESS packages to S3${NC}\n"
fi

# Generate deployment manifest
MANIFEST_FILE="$PACKAGE_DIR/deployment-manifest.json"
log "${BLUE}Generating deployment manifest...${NC}"

cat > "$MANIFEST_FILE" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "environment": "$ENV",
  "packages": [
EOF

FIRST=true
for ZIP_FILE in "$PACKAGE_DIR"/*.zip; do
    if [ -f "$ZIP_FILE" ]; then
        FILENAME=$(basename "$ZIP_FILE")
        SIZE=$(stat -f%z "$ZIP_FILE" 2>/dev/null || stat -c%s "$ZIP_FILE" 2>/dev/null || echo "0")
        HASH=$(md5sum "$ZIP_FILE" 2>/dev/null | cut -d' ' -f1 || md5 -q "$ZIP_FILE" 2>/dev/null || echo "unknown")

        if [ "$FIRST" = true ]; then
            FIRST=false
        else
            echo "," >> "$MANIFEST_FILE"
        fi

        cat >> "$MANIFEST_FILE" << EOF
    {
      "name": "${FILENAME%.zip}",
      "filename": "$FILENAME",
      "size": $SIZE,
      "md5": "$HASH"
    }
EOF
    fi
done

cat >> "$MANIFEST_FILE" << EOF

  ],
  "s3_bucket": "$BUCKET",
  "total_packages": $SUCCESS
}
EOF

log "${GREEN}✓ Manifest created: $MANIFEST_FILE${NC}\n"

# Print final summary
log "${GREEN}========================================${NC}"
log "${GREEN}Packaging Complete!${NC}"
log "${GREEN}========================================${NC}"
log "Package directory: $PACKAGE_DIR"
log "Total packages: $SUCCESS"
if [ "$UPLOAD" = true ]; then
    log "S3 location: s3://$BUCKET/lambda-packages/"
fi
log "Log file: $LOG_FILE"
log "Manifest: $MANIFEST_FILE"
log "${GREEN}========================================${NC}\n"

# List all packages
log "${BLUE}Created Packages:${NC}"
for ZIP_FILE in "$PACKAGE_DIR"/*.zip; do
    if [ -f "$ZIP_FILE" ]; then
        SIZE=$(du -h "$ZIP_FILE" | cut -f1)
        log "  • $(basename "$ZIP_FILE") ($SIZE)"
    fi
done
log ""

# Check package sizes against Lambda limits
log "${BLUE}Checking package sizes against Lambda limits...${NC}"
LIMIT_WARNING=false
for ZIP_FILE in "$PACKAGE_DIR"/*.zip; do
    if [ -f "$ZIP_FILE" ]; then
        SIZE_BYTES=$(stat -f%z "$ZIP_FILE" 2>/dev/null || stat -c%s "$ZIP_FILE" 2>/dev/null || echo "0")
        SIZE_MB=$((SIZE_BYTES / 1024 / 1024))

        if [ $SIZE_MB -gt 50 ]; then
            log "${RED}  ✗ $(basename "$ZIP_FILE"): ${SIZE_MB}MB (exceeds 50MB direct upload limit)${NC}"
            log "${YELLOW}    → Must upload to S3 and deploy from there${NC}"
            LIMIT_WARNING=true
        elif [ $SIZE_MB -gt 10 ]; then
            log "${YELLOW}  ⚠ $(basename "$ZIP_FILE"): ${SIZE_MB}MB (approaching limit)${NC}"
        else
            log "${GREEN}  ✓ $(basename "$ZIP_FILE"): ${SIZE_MB}MB${NC}"
        fi
    fi
done

if [ "$LIMIT_WARNING" = true ]; then
    log "\n${YELLOW}Note: Some packages exceed the 50MB direct upload limit.${NC}"
    log "${YELLOW}Use --upload flag to upload to S3 for deployment.${NC}"
fi

log "\n${GREEN}✅ All Lambda functions packaged successfully!${NC}\n"

# Exit with appropriate code
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
